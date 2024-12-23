import requests
from bs4 import BeautifulSoup

# URL для запроса
url = "https://r-vision.omnidesk.ru/knowledge_base/item/339231?sid=72288"

# Заголовки с куками (замените на ваши реальные данные)
headers = {
    "PHPSESSID": "vkt06m86c316tsufbddhb91glb"  # Вставьте куки сюда
}

# Выполняем запрос к странице
response = requests.get(url, cookies=headers)

# Проверяем успешность запроса
if response.status_code == 200:
    # Парсинг HTML с помощью BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

    # Извлечение навигационного пути
    breadcrumbs = soup.find_all("li", class_="breadcrumbs__item")
    navigation = {
        'база': breadcrumbs[0].get_text(strip=True) if len(breadcrumbs) > 0 else "Не найдено",
        'раздел': breadcrumbs[1].get_text(strip=True) if len(breadcrumbs) > 1 else "Не найдено",
        'категория': breadcrumbs[2].get_text(strip=True) if len(breadcrumbs) > 2 else "Не найдено"
    }

    # Вывод навигации
    print("База:", navigation['база'])
    print("Раздел:", navigation['раздел'])
    print("Категория:", navigation['категория'])
    print()

    # Извлечение заголовка
    title_tag = soup.find("h1", class_="kb-article-title")
    title = title_tag.get_text(strip=True) if title_tag else "Заголовок не найден"

    # Извлечение описания проблемы
    problem_div = soup.find("div", class_="problem")
    problem_description = (
        " ".join(problem_div.stripped_strings)
        if problem_div 
        else "Описание проблемы не найдено"
    )

    # Извлечение решения и изображений
    solution_divs = soup.find_all("div", class_="solution")
    if solution_divs:
        # Собираем весь текст из всех solution div'ов
        solution_text = " ".join(" ".join(div.stripped_strings) for div in solution_divs)
        
        # Собираем все изображения из всех solution div'ов
        image_urls = []
        for div in solution_divs:
            images = div.find_all("img")
            image_urls.extend([img.get('src', '') for img in images if img.get('src')])
        
        solution = {
            'text': solution_text,
            'images': image_urls
        }
    else:
        solution = {
            'text': "Решение не найдено",
            'images': []
        }

    # Вывод результата
    print("Заголовок:", title)
    print("Описание проблемы:", problem_description)
    print("Решение:", solution['text'])
    if solution['images']:
        print("\nИзображения в решении:")
        for url in solution['images']:
            print(url)
else:
    print(f"Ошибка запроса: {response.status_code}")
