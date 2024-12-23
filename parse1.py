import os
import shutil
import requests
from bs4 import BeautifulSoup, Tag
from pathlib import Path
from dotenv import load_dotenv
from requests.cookies import RequestsCookieJar

# Загружаем переменные окружения из .env
load_dotenv()

class KnowledgeBaseParser:
    def __init__(self):
        self.base_url = os.getenv('BASE_URL', 'https://r-vision.omnidesk.ru/knowledge_base/item/')
        # Создаем правильный объект для cookies
        self.cookies = requests.cookies.RequestsCookieJar()
        self.cookies.set('PHPSESSID', os.getenv('PHPSESSID'))
        self.image_counter = 1
        self.base_dir = "knowledge_base"
        
    def get_soup(self, url):
        """Получает BeautifulSoup объект для URL"""
        try:
            response = requests.get(url, cookies=self.cookies)
            if response.status_code == 200:
                return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            print(f"Ошибка при получении страницы {url}: {e}")
        return None

    def clean_directory(self):
        """Очищает базовую директорию"""
        if os.path.exists(self.base_dir):
            shutil.rmtree(self.base_dir)
        os.makedirs(self.base_dir)
        os.makedirs(os.path.join(self.base_dir, "images"))

    def download_image(self, url, article_title):
        """Скачивает изображение и сохраняет его с названием статьи и порядковым номером"""
        try:
            response = requests.get(url)
            if response.status_code == 200:
                # Создаем безопасное имя файла из названия статьи
                safe_title = self.sanitize_filename(article_title)
                image_filename = f"{safe_title}-{self.image_counter}.jpg"
                image_path = os.path.join(self.base_dir, "images", image_filename)
                
                with open(image_path, 'wb') as f:
                    f.write(response.content)
                current_number = self.image_counter
                self.image_counter += 1
                return current_number
        except Exception as e:
            print(f"Ошибка при скачивании изображения {url}: {e}")
        return None

    def create_article_path(self, navigation):
        """Создает путь для статьи на основе навигации"""
        path_parts = [
            self.base_dir,
            self.sanitize_filename(navigation['база']),
            self.sanitize_filename(navigation['раздел']),
            self.sanitize_filename(navigation['категория'])
        ]
        current_path = Path("")
        for part in path_parts:
            current_path = current_path / part
            if not os.path.exists(current_path):
                os.makedirs(current_path)
        return current_path

    @staticmethod
    def sanitize_filename(filename):
        """Очищает строку для использования в качестве имени файла"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip()

    def parse_page(self, url):
        """Парсит страницу и сохраняет статью"""
        response = requests.get(url, cookies=self.cookies)
        if response.status_code != 200:
            print(f"Ошибка запроса: {response.status_code}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')

        # Извлекаем навигацию
        breadcrumbs = soup.find_all("li", class_="breadcrumbs__item")
        navigation = {
            'база': breadcrumbs[0].get_text(strip=True) if len(breadcrumbs) > 0 else "Без категории",
            'раздел': breadcrumbs[1].get_text(strip=True) if len(breadcrumbs) > 1 else "Без раздела",
            'категория': breadcrumbs[2].get_text(strip=True) if len(breadcrumbs) > 2 else "Без подраздела"
        }

        # Создаем путь для статьи
        article_path = self.create_article_path(navigation)

        # Извлекаем содержимое
        title_elem = soup.find("h1", class_="kb-article-title")
        if not title_elem:
            print("Заголовок статьи не найден")
            return
        title = title_elem.get_text(strip=True)
        problem_div = soup.find("div", class_="problem")
        problem_text = " ".join(problem_div.stripped_strings) if problem_div else "Описание проблемы не найдено"
        
        solution_divs = soup.find_all("div", class_="solution")
        solution_text = ""
        image_references = []

        if solution_divs:
            for div in solution_divs:
                # Обрабатываем изображения
                for img in div.find_all("img"):
                    if img.get('src'):
                        image_num = self.download_image(img['src'], title)
                        if image_num:
                            image_references.append(f"${image_num}")
                            img.replace_with(f"${image_num}")
                
                solution_text += " ".join(div.stripped_strings) + "\n"

        content_div = soup.find("div", class_="kb-article-content clearfix")
        if not content_div:
            print("Содержание статьи не найдено")
            return
        
        # Создаем копию для работы с текстом
        content_text = ""
        image_references = []
        
        # Обрабатываем контент последовательно
        for element in content_div.children:
            if isinstance(element, Tag):
                # Обрабатываем изображения
                for img in element.find_all("img"):
                    if img.get('src'):
                        image_num = self.download_image(img['src'], title)
                        if image_num:
                            image_references.append(f"${image_num}")
                            img.replace_with(f"${image_num}")
                
                # Добавляем текст с сохранением структуры
                text = " ".join(element.stripped_strings)
                if text:
                    content_text += text + "\n\n"
            elif str(element).strip():
                content_text += str(element).strip() + "\n\n"

        # Формируем метаданные и содержимое статьи
        article_content = [
            "# Метаданные",
            f"# URL: {url}",
            f"# Название: {title}",
            f"# База: {navigation['база']}",
            f"# Раздел: {navigation['раздел']}",
            f"# Категория: {navigation['категория']}",
            "",
            "# Содержание",
            content_text.strip()
        ]

        # Сохраняем статью
        article_file = article_path / f"{self.sanitize_filename(title)}.txt"
        with open(article_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(article_content))

    def get_article_title(self, url):
        """Получает заголовок статьи"""
        soup = self.get_soup(url)
        if soup:
            title = soup.find("h1", class_="kb-article-title")
            return title.get_text(strip=True) if title else None
        return None

    def get_article_content(self, url):
        """Получает содержимое статьи"""
        soup = self.get_soup(url)
        if soup:
            content = soup.find("div", class_="kb-article-content")
            return content.get_text(strip=True) if content else None
        return None

    def get_image_count(self, url):
        """Подсчитывает количество изображений в статье"""
        soup = self.get_soup(url)
        if not soup:
            return 0
        content = soup.find("div", class_="kb-article-content")
        if isinstance(content, Tag):
            return len(content.find_all("img"))
        return 0

def main():
    parser = KnowledgeBaseParser()
    parser.clean_directory()
    
    # URL для парсинга можно также вынести в .env
    article_url = os.getenv('ARTICLE_URL', 'https://r-vision.omnidesk.ru/knowledge_base/item/339231?sid=72288')
    parser.parse_page(article_url)

if __name__ == "__main__":
    main()
