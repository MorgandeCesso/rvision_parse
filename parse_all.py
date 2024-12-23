import os
import time
import requests
import logging
from bs4 import BeautifulSoup, Tag
from parse1 import KnowledgeBaseParser
from urllib.parse import urljoin
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('parser.log'),
        logging.StreamHandler()
    ]
)

class KnowledgeBaseCollector:
    def __init__(self):
        self.base_url = "https://r-vision.omnidesk.ru/"
        # Создаем правильный объект для cookies
        self.cookies = requests.cookies.RequestsCookieJar()
        self.cookies.set('PHPSESSID', os.getenv('PHPSESSID'))
        self.article_links = []
        self.parser = KnowledgeBaseParser()
        self.processed_articles = set()  # Для отслеживания обработанных статей

    def file_exists(self, filepath):
        """Проверяет существование файла"""
        return os.path.exists(filepath)

    def should_update_article(self, article_url):
        """Проверяет, нужно ли обновлять статью"""
        try:
            # Получаем текущее содержимое статьи через парсер
            new_content = self.parser.get_article_content(article_url)
            if not new_content:
                logging.warning(f"Не удалось получить содержимое статьи {article_url}")
                return True
            
            # Получаем название статьи для формирования пути файла
            title = self.parser.get_article_title(article_url)
            if not title:
                logging.warning(f"Не удалось получить заголовок статьи {article_url}")
                return True
            
            safe_title = self.parser.sanitize_filename(title)
            article_path = Path(self.parser.base_dir) / f"{safe_title}.txt"
            
            # Если файла нет - нужно создать
            if not self.file_exists(article_path):
                logging.info(f"Статья {article_url} отсутствует на диске")
                return True
            
            # Читаем существующий файл
            try:
                with open(article_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                
                # Сравниваем содержимое
                if existing_content.strip() != new_content.strip():
                    logging.info(f"Содержимое статьи {article_url} изменилось")
                    return True
                
                # Проверяем наличие всех изображений
                image_count = self.parser.get_image_count(article_url)
                for i in range(1, image_count + 1):
                    img_path = Path(self.parser.base_dir) / "images" / f"{safe_title}-{i}.jpg"
                    if not self.file_exists(img_path):
                        logging.info(f"Отсутствует изображение {i} для статьи {article_url}")
                        return True
                
                logging.info(f"Статья {article_url} не требует обновления")
                return False
            
            except Exception as e:
                logging.warning(f"Ошибка при чтении существующей статьи {article_url}: {e}")
                return True
            
        except Exception as e:
            logging.warning(f"Ошибка при проверке статьи {article_url}: {e}")
            return True

    def process_article(self, article_url):
        """Обрабатывает статью с проверкой на существование"""
        try:
            if article_url in self.processed_articles:
                logging.info(f"Статья {article_url} уже была обработана")
                return

            response = requests.get(article_url, cookies=self.cookies)
            if response.status_code != 200:
                logging.error(f"Ошибка получения статьи {article_url}: {response.status_code}")
                return

            if not self.should_update_article(article_url):
                logging.info(f"Статья {article_url} не требует обновления")
                return

            # Парсим статью
            self.parser.parse_page(article_url)
            self.processed_articles.add(article_url)
            logging.info(f"Статья {article_url} успешно обработана")

        except Exception as e:
            logging.error(f"Ошибка при обработке статьи {article_url}: {e}")

    def get_section_links(self):
        """Получает все ссылки на разделы с главной страницы"""
        try:
            response = requests.get(self.base_url, cookies=self.cookies)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                sections = soup.find_all("a", class_="kb-title-link")
                links = []
                
                logging.info(f"Найдено {len(sections)} основных разделов")
                
                for section in sections:
                    try:
                        section_block = section.find_parent("div", class_="knowBaze")
                        if section_block:
                            categories = section_block.find_all("a", class_="knowBaze_section_elem")
                            logging.debug(f"В разделе найдено {len(categories)} категорий")
                            for category in categories:
                                link = category.get('href')
                                if link:
                                    full_link = urljoin(self.base_url, link)
                                    links.append(full_link)
                                    logging.debug(f"Добавлена категория: {full_link}")
                    except Exception as section_error:
                        logging.error(f"Ошибка при обработке раздела: {section_error}")
                        continue
                        
                logging.info(f"Всего найдено {len(links)} категорий")
                return links
            else:
                logging.error(f"Ошибка при получении главной страницы: {response.status_code}")
                return []
        except requests.Timeout:
            logging.error("Таймаут при получении главной страницы")
            return []
        except Exception as e:
            logging.error(f"Критическая ошибка при получении ссылок разделов: {e}")
            return []

    def get_article_links(self, section_url):
        """Получает все ссылки на статьи из раздела"""
        try:
            logging.info(f"Получаем статьи из раздела: {section_url}")
            response = requests.get(section_url, cookies=self.cookies, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                articles = soup.find_all("a", class_="kb-artile-list__item")
                links = []
                
                for article in articles:
                    try:
                        link = article.get('href')
                        if link:
                            full_link = urljoin(self.base_url, link)
                            links.append(full_link)
                            logging.debug(f"Найдена статья: {full_link}")
                    except Exception as article_error:
                        logging.error(f"Ошибка при обработке ссылки на статью: {article_error}")
                        continue
                
                # Обработка пагинации
                try:
                    show_more = soup.find("a", class_="btn btn--gray", 
                                        onclick=lambda x: 'showMoreKnowledge' in str(x) if x else False)
                    if show_more:
                        offset = soup.find("input", {"name": "offset_knowledge"})
                        if offset and isinstance(offset, Tag):
                            offset_value = int(offset.get('value', '0'))
                            # Получаем базовый URL без параметров
                            base_url = section_url.split('?')[0]
                            # Формируем новый URL с корректным offset
                            next_url = f"{base_url}?offset={offset_value}"
                            logging.info(f"Переход к следующей странице: {next_url}")
                            # Проверяем, что URL не повторяется
                            if next_url != section_url:
                                links.extend(self.get_article_links(next_url))
                except Exception as pagination_error:
                    logging.error(f"Ошибка при обработке пагинации: {pagination_error}")
                
                logging.info(f"Найдено {len(links)} статей в разделе {section_url}")
                return links
            else:
                logging.error(f"Ошибка при получении раздела {section_url}: {response.status_code}")
                return []
        except requests.Timeout:
            logging.error(f"Таймаут при получении раздела {section_url}")
            return []
        except Exception as e:
            logging.error(f"Критическая ошибка при получении ссылок статей: {e}")
            return []

    def collect_all_articles(self):
        """Собирает все статьи с сайта"""
        section_links = self.get_section_links()
        logging.info(f"Начинаем сбор статей из {len(section_links)} разделов")

        for section_url in section_links:
            article_links = self.get_article_links(section_url)
            for article_url in article_links:
                self.process_article(article_url)
            time.sleep(1)

        logging.info(f"Обработка завершена. Всего обработано статей: {len(self.processed_articles)}")
        return self.processed_articles

def main():
    collector = KnowledgeBaseCollector()
    collector.collect_all_articles()

if __name__ == "__main__":
    main() 