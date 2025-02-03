import pygame
import random
import sqlite3
import time
import os
from datetime import datetime
import sys

sys.setrecursionlimit(2500)

# Константы
WIDTH, HEIGHT = 800, 600
EASY_SIZE = (9, 9, 10)
MEDIUM_SIZE = (16, 16, 40)
HARD_SIZE = (30, 16, 99)
MINE_COLORS = {
    0: (0, 0, 0),
    1: (0, 0, 255),
    2: (0, 128, 0),
    3: (255, 0, 0),
    4: (0, 0, 128),
    5: (128, 0, 0),
    6: (0, 128, 128),
    7: (0, 0, 0),
    8: (128, 128, 128)
}

# Цвета
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RR = (125, 125, 125)
GRAY = (180, 180, 180)
DARK_GRAY = (135, 135, 135)
LIGHT_GRAY = (230, 230, 230)
RED = (255, 0, 0)
GREEN = (30, 220, 30)
BLUE = (0, 0, 255)
COLORR = (100, 100, 255)

# Загрузка изображений
flag_image = pygame.image.load(os.path.join('flag.png'))
mine_image = pygame.image.load(os.path.join('mine.png'))

all_sprites = pygame.sprite.Group()


class Bomb(pygame.sprite.Sprite):
    image = mine_image

    def __init__(self, all_sprites):
        super().__init__(all_sprites)
        self.image = Bomb.image
        self.rect = self.image.get_rect()
        self.rect.x = random.randrange(900)
        self.rect.y = random.randrange(900)

    def update(self):
        self.rect = self.rect.move(random.randrange(3) - 1,
                                   random.randrange(3) - 1)


def create_db():
    """Создает базу данных для хранения рекордов, если она не существует."""
    try:
        conn = sqlite3.connect('minesweeper_records.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT,
                difficulty TEXT,
                time INTEGER,
                date TEXT
            )
        ''')

        cursor.execute("PRAGMA table_info(records)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'date' not in columns:
            cursor.execute("ALTER TABLE records ADD COLUMN date TEXT")
            conn.commit()

        conn.commit()
        return conn, cursor
    except sqlite3.Error as e:
        print(f"Ошибка при работе с базой данных: {e}")
        return None, None


def save_record(cursor, conn, name, difficulty, time):
    """Сохраняет рекорд в базу данных."""
    date = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    try:
        cursor.execute("INSERT INTO records (player_name, difficulty, time, date) VALUES (?, ?, ?, ?)",
                       (name, difficulty, time, date))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Ошибка при сохранении рекорда: {e}")


def load_records(cursor):
    """Загружает рекорды из базы данных."""
    try:
        cursor.execute("SELECT player_name, difficulty, time, date FROM records")
        records = cursor.fetchall()
        # Сортируем по уровню сложности, а затем по времени
        records.sort(key=lambda record: (
            {"Легкий": 0, "Средний": 1, "Сложный": 2, "Пользовательский": 3}[record[1]],
            record[2]
        ))
        return records
    except sqlite3.Error as e:
        print(f"Ошибка при загрузке рекордов: {e}")
        return []


# --- Функции игры ---
def generate_mines(width, height, num_mines):
    """Генерирует случайные координаты мин."""
    total_cells = width * height
    if num_mines >= total_cells:
        raise ValueError("Слишком много мин для поля!")
    return random.sample(range(total_cells), num_mines)


def get_cell_coords(index, width):
    """Преобразует индекс в координаты клетки."""
    return index % width, index // width


def count_adjacent_mines(grid, x, y):
    """Считает количество мин вокруг клетки (x, y)."""
    count = 0
    for i in range(max(0, x - 1), min(x + 2, len(grid[0]))):
        for j in range(max(0, y - 1), min(y + 2, len(grid))):
            if grid[j][i] == '*':
                count += 1
    return count


def open_empty_cells(grid, revealed, x, y):
    """Открывает пустые клетки рекурсивно."""
    if not (0 <= x < len(grid[0]) and 0 <= y < len(grid)) or (x, y) in revealed:
        return
    revealed.add((x, y))
    if grid[y][x] != 0:
        return
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            open_empty_cells(grid, revealed, x + dx, y + dy)


# --- Функции отрисовки ---
def draw_grid(screen, grid, revealed, flagged, width, height, cell_size, game_over=False, mine_indices=[], offset_x=0,
              offset_y=0, start_time=0, num_mines=0, flagged_count=0, conn=None, cursor=None, win=False,
              game_active=True):
    """Рисует игровое поле."""
    for x in range(width):
        for y in range(height):
            rect = pygame.Rect(x * cell_size + offset_x, y * cell_size + offset_y, cell_size, cell_size)
            cell_color = GRAY
            if (x, y) in revealed and grid[y][x] != '*':
                cell_color = DARK_GRAY
            pygame.draw.rect(screen, cell_color, rect)
            pygame.draw.rect(screen, LIGHT_GRAY, rect, 1)

            if (x, y) in flagged:
                # Рисуем флажок
                screen.blit(pygame.transform.scale(flag_image, (cell_size, cell_size)),
                            (x * cell_size + offset_x, y * cell_size + offset_y))
                # Если игра окончена и флаг на мине - оставляем как есть
                if game_over and (x, y) not in [get_cell_coords(index, width) for index in mine_indices]:
                    # Рисуем перечеркнутый флаг если флаг не на мине
                    pygame.draw.line(screen, BLACK, (x * cell_size + offset_x, y * cell_size + offset_y),
                                     ((x + 1) * cell_size + offset_x, (y + 1) * cell_size + offset_y), 3)
                    pygame.draw.line(screen, BLACK, ((x + 1) * cell_size + offset_x, y * cell_size + offset_y),
                                     (x * cell_size + offset_x, (y + 1) * cell_size + offset_y), 3)

            elif (x, y) in revealed:
                if grid[y][x] == '*':
                    # Рисуем мину если открыли
                    screen.blit(pygame.transform.scale(mine_image, (cell_size, cell_size)),
                                (x * cell_size + offset_x, y * cell_size + offset_y))
                else:
                    if grid[y][x] != 0:
                        font_size = int(cell_size * 1)
                        font = pygame.font.Font(None, font_size)
                        text = font.render(str(grid[y][x]), True, MINE_COLORS[grid[y][x]])
                        text_rect = text.get_rect(center=rect.center)
                        screen.blit(text, text_rect)
            # Показываем все мины, если игра окончена и клетка не открыта
            elif game_over and (x, y) in [get_cell_coords(index, width) for index in mine_indices]:
                mine_size = int(cell_size * 0.9)
                mine_offset = (cell_size - mine_size) // 2
                screen.blit(pygame.transform.scale(mine_image, (mine_size, mine_size)),
                            (x * cell_size + offset_x + mine_offset, y * cell_size + offset_y + mine_offset))

    # Отображение времени и оставшихся мин
    font = pygame.font.Font(None, 30)
    elapsed_time = int(time.time() - start_time)
    mines_left = num_mines - flagged_count
    time_text = font.render(f"Время: {elapsed_time} sec", True, BLACK)
    mines_text = font.render(f"Мин осталось: {mines_left}", True, BLACK)
    screen.blit(time_text, (30, screen.get_height() - 80))
    screen.blit(mines_text, (screen.get_width() - 930, screen.get_height() - 40))

    # Отрисовываем кнопки
    button_width = 220
    button_height = 30
    button_y = screen.get_height() - 90
    draw_button(screen, "Новая игра", 340, button_y, button_width, button_height, GRAY, COLORR,
                lambda: start_game(screen, conn, cursor, width, height, num_mines), game_active)
    draw_button(screen, "Изменить сложность", screen.get_width() - button_width - 400, button_y + 40, button_width,
                button_height, GRAY, COLORR, lambda: main_menu(), game_active)

    pygame.display.flip()


def draw_button(screen, text, x, y, width, height, color, hover_color, action, game_active=True):
    """Рисует кнопку."""
    mouse = pygame.mouse.get_pos()
    click = pygame.mouse.get_pressed()
    rect = pygame.Rect(x, y, width, height)
    color = hover_color if rect.collidepoint(mouse) else color
    pygame.draw.rect(screen, color, rect)
    font = pygame.font.Font(None, 30)
    text_surf = font.render(text, True, BLACK)
    text_rect = text_surf.get_rect(center=rect.center)
    screen.blit(text_surf, text_rect)
    if rect.collidepoint(mouse) and click[0] == 1:
        action()


def show_end_screen(screen, message, grid, revealed, flagged, width, height, cell_size, mine_indices, offset_x,
                    offset_y, start_time, num_mines, flag, conn, cursor):
    """Отображает экран окончания игры с рамкой вокруг текста."""
    screen.fill(LIGHT_GRAY)
    draw_grid(screen, grid, revealed, flagged, width, height, cell_size, True, mine_indices, offset_x, offset_y,
              start_time, num_mines, len(flagged), game_active=False)
    font = pygame.font.Font(None, 28)
    text_surf = font.render(message, True, GREEN if flag else RED)
    text_rect = text_surf.get_rect(center=(screen.get_width() - 200, screen.get_height() - 80))
    screen.blit(text_surf, text_rect)

    if flag:
        text_surf2 = font.render("Коснитесь здесь, чтобы ввести имя", True, RR)
        text_rect2 = text_surf2.get_rect(center=(screen.get_width() - 200, screen.get_height() - 40))

        padding = 10
        frame_rect = text_rect2.inflate(padding * 2, padding * 2)

        pygame.draw.rect(screen, BLACK, frame_rect, 2)


        screen.blit(text_surf2, text_rect2)


    game_active = False

    button_width = 220
    button_height = 30
    button_y = screen.get_height() - 90
    button_rect_1 = pygame.Rect(340, button_y, button_width, button_height)
    button_rect_2 = pygame.Rect(screen.get_width() - button_width - 400, button_y + 40, button_width, button_height)
    draw_button(screen, "Новая игра", 340, button_y, button_width, button_height, GRAY, COLORR,
                lambda: start_game(screen, conn, cursor, width, height, num_mines), game_active)
    draw_button(screen, "Изменить сложность", screen.get_width() - button_width - 400, button_y + 40, button_width,
                button_height, GRAY, COLORR, lambda: main_menu(), game_active)


    pygame.display.flip()

    if flag:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if text_rect2.collidepoint(event.pos) and event.button == 1:
                        return
                    if event.button == 1 and button_rect_1.collidepoint(event.pos):
                        start_game(screen, conn, cursor, width, height, num_mines)
                        return
                    if event.button == 1 and button_rect_2.collidepoint(event.pos):
                        main_menu()
                        return
    else:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1 and button_rect_1.collidepoint(event.pos):
                        start_game(screen, conn, cursor, width, height, num_mines)
                        return
                    if event.button == 1 and button_rect_2.collidepoint(event.pos):
                        main_menu()
                        return

def get_player_name(screen):
    """Открывает окно ввода имени игрока."""
    font = pygame.font.Font(None, 30)
    input_box = pygame.Rect(screen.get_width() // 2 - 100, screen.get_height() // 2 - 20, 200, 40)
    color_inactive = DARK_GRAY
    color_active = GRAY
    color = color_inactive
    active = False
    text = ''
    done = False

    prompt_font = pygame.font.Font(None, 28)
    prompt_text = prompt_font.render("Введите имя:", True, BLACK)
    prompt_rect = prompt_text.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2 - 60))

    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.MOUSEBUTTONDOWN:
                if input_box.collidepoint(event.pos):
                    active = not active
                else:
                    active = False
                color = color_active if active else color_inactive
            if event.type == pygame.KEYDOWN:
                if active:
                    if event.key == pygame.K_RETURN:
                        done = True
                    elif event.key == pygame.K_BACKSPACE:
                        text = text[:-1]
                    else:
                        text += event.unicode

        screen.fill(LIGHT_GRAY)
        screen.blit(prompt_text, prompt_rect)
        txt_surface = font.render(text, True, BLACK)
        width = max(200, txt_surface.get_width() + 10)
        input_box.w = width
        pygame.draw.rect(screen, color, input_box, 2)
        screen.blit(txt_surface, (input_box.x + 5, input_box.y + 5))
        pygame.display.flip()
    if text:
        return text
    return None


# --- Функции игрового процесса ---
def play_game(screen, width, height, num_mines, cell_size, offset_x, offset_y, conn, cursor):
    """Основная функция игры."""
    grid = [[0 for _ in range(width)] for _ in range(height)]
    mine_indices = generate_mines(width, height, num_mines)
    for index in mine_indices:
        x, y = get_cell_coords(index, width)
        grid[y][x] = '*'
    for y in range(height):
        for x in range(width):
            if grid[y][x] != '*':
                grid[y][x] = count_adjacent_mines(grid, x, y)
    revealed = set()
    flagged = set()
    start_time = time.time()
    running = True
    game_over = False
    win = False
    game_active = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                return None, None, False, grid, revealed, flagged, cell_size, mine_indices, offset_x, offset_y, start_time, num_mines, None
            if event.type == pygame.MOUSEBUTTONDOWN:
                if not game_active:
                    continue  # Остаемся в игровом окне при нажатии не на кнопки
                x, y = event.pos
                cell_x = (x - offset_x) // cell_size
                cell_y = (y - offset_y) // cell_size
                if event.button == 1:  # Левая кнопка
                    if ((cell_x, cell_y) in [get_cell_coords(i, width) for i in mine_indices] and
                            (cell_x, cell_y) not in flagged):
                        game_over = True
                        running = False
                        win = False
                        game_active = False
                        break
                    elif (cell_x, cell_y) not in revealed and (cell_x, cell_y) not in flagged:
                        open_empty_cells(grid, revealed, cell_x, cell_y)
                elif event.button == 3:  # Правая кнопка
                    if (cell_x, cell_y) not in revealed:
                        if (cell_x, cell_y) in flagged:
                            flagged.remove((cell_x, cell_y))
                        else:
                            flagged.add((cell_x, cell_y))
        screen.fill(WHITE)
        draw_grid(screen, grid, revealed, flagged, width, height, cell_size, offset_x=offset_x, offset_y=offset_y,
                  start_time=start_time, num_mines=num_mines, flagged_count=len(flagged), conn=conn, cursor=cursor,
                  game_over=game_over, win=win, game_active=game_active)
        pygame.display.flip()
        if len(revealed) == width * height - num_mines and not game_over:
            end_time = time.time()
            elapsed_time = int(end_time - start_time)
            print("You Win! Time:", elapsed_time)
            running = False
            win = True
            game_active = False
            break
    if game_over:
        flag = 0
        return "Игра окончена! Вы проиграли", None, False, grid, revealed, flagged, cell_size, mine_indices, offset_x, offset_y, start_time, num_mines, flag
    elif win:
        flag = 1
        return "Поздравляем! Вы выиграли", elapsed_time, True, grid, revealed, flagged, cell_size, mine_indices, offset_x, offset_y, start_time, num_mines, flag
    return None, None, False, None, None, None, None, None, None, None, None, None, False


def show_highscores(screen, cursor, records):
    """Показывает таблицу рекордов."""
    screen.fill(LIGHT_GRAY)
    font = pygame.font.Font(None, 24)
    y = 50

    # Разделение рекордов по сложности
    easy_records = [rec for rec in records if rec[1] == "Легкий"]
    medium_records = [rec for rec in records if rec[1] == "Средний"]
    hard_records = [rec for rec in records if rec[1] == "Сложный"]
    custom_records = [rec for rec in records if rec[1] == "Пользовательский"]

    # Отображение рекордов с заголовками
    y = display_records(screen, "Легкий", easy_records, y, font)
    y = display_records(screen, "Средний", medium_records, y, font)
    y = display_records(screen, "Сложный", hard_records, y, font)
    y = display_records(screen, "Пользовательский", custom_records, y, font)

    # Кнопка "Назад"
    button_width = 120
    button_height = 30
    button_x = screen.get_width() // 2 - button_width // 2
    button_y = screen.get_height() - button_height - 20
    back_button_rect = pygame.Rect(button_x, button_y, button_width, button_height)


    running = True
    while running:
        mouse = pygame.mouse.get_pos()

        if back_button_rect.collidepoint(mouse):
            back_button_color = COLORR
        else:
            back_button_color = DARK_GRAY

        draw_button(screen, "Назад", button_x, button_y, button_width, button_height, back_button_color, COLORR,
                    main_menu, False)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and back_button_rect.collidepoint(event.pos):
                    running = False
                    return

def display_records(screen, difficulty, records, start_y, font):
    """Отображает рекорды для заданной сложности."""
    y = start_y
    text = font.render(f"{difficulty}:", True, BLACK)
    screen.blit(text, (50, y))
    # Получаем координаты текста
    text_rect = text.get_rect(topleft=(50, y))
    # Рисуем подчеркивание под текстом
    pygame.draw.line(screen, BLACK, (text_rect.left, text_rect.bottom + 2), (text_rect.right, text_rect.bottom + 2), 2)
    y += 30
    for name, diff, time, date in records:
        text = font.render(f"{name} - {time} сек - {date}", True, BLACK)
        screen.blit(text, (70, y))
        y += 25
    return y + 10


def main_menu():
    """Главное меню."""
    pygame.init()
    side = int(max(WIDTH, HEIGHT) * 1.2)
    screen = pygame.display.set_mode((side, side))
    pygame.display.set_caption("Сапер")
    conn, cursor = create_db()
    if conn is None:
        return
    button_width = 200
    button_height = 40
    button_x = side // 2 - button_width // 2
    button_y_start = int(side / 2.2)

    # Создаем экземпляры Bomb с координатами под кнопками
    all_sprites.empty()
    for i in range(50):
        Bomb(all_sprites)

    running = True
    font_author = pygame.font.Font(None, 26)
    font_version = pygame.font.Font(None, 26

                                    )

    while running:
        screen.fill(LIGHT_GRAY)
        all_sprites.draw(screen)
        all_sprites.update()

        # Надпись об авторах
        authors_text = font_author.render("Created by: Бородина Катя, Попов Сережа", True, BLACK)
        authors_rect = authors_text.get_rect(bottomleft=(10, side - 30))  # Отступ для первой надписи
        screen.blit(authors_text, authors_rect)

        # Надпись о версии
        version_text = font_version.render("Version: 1.0", True, BLACK)
        version_rect = version_text.get_rect(bottomleft=(10, side - 10))  # Отступ для второй надписи
        screen.blit(version_text, version_rect)

        draw_button(screen, "Легкий", button_x, button_y_start, button_width, button_height, DARK_GRAY, COLORR,
                    lambda: start_game(screen, conn, cursor, *EASY_SIZE))
        draw_button(screen, "Средний", button_x, button_y_start + 50, button_width, button_height, DARK_GRAY, COLORR,
                    lambda: start_game(screen, conn, cursor, *MEDIUM_SIZE))
        draw_button(screen, "Сложный", button_x, button_y_start + 100, button_width, button_height, DARK_GRAY, COLORR,
                    lambda: start_game(screen, conn, cursor, *HARD_SIZE))
        draw_button(screen, "Пользовательский", button_x, button_y_start + 150, button_width, button_height,
                    DARK_GRAY, COLORR, lambda: custom_game_settings(screen, conn, cursor))
        draw_button(screen, "Таблица рекордов", button_x, button_y_start + 200, button_width, button_height,
                    DARK_GRAY, COLORR, lambda: show_highscores(screen, cursor, load_records(cursor)))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
    pygame.quit()
    conn.close()

def start_game(screen, conn, cursor, width, height, num_mines):
    """Запускает игру с выбранными параметрами."""
    pygame.init()
    side = int(max(WIDTH, HEIGHT) * 1.2)
    if (width, height, num_mines) == HARD_SIZE:
        screen = pygame.display.set_mode((side, side))
        cell_size = min(side // (width + 2), side // (height + 2))
        offset_x = (side - cell_size * width) // 2
        offset_y = (side - cell_size * height) // 2
    else:
        screen = pygame.display.set_mode((side, int(side * 0.9)))
        cell_size = min(side // width, (int(side * 0.9) - 100) // height)
        offset_x = (side - cell_size * width) // 2
        offset_y = (int(side * 0.9) - cell_size * height - 100) // 2
    message, elapsed_time, win, grid, revealed, flagged, cell_size, mine_indices, offset_x, offset_y, start_time, num_mines, flag = play_game(
        screen, width, height, num_mines, cell_size, offset_x, offset_y, conn=conn, cursor=cursor)
    if message is not None:
        show_end_screen(screen, message, grid, revealed, flagged, width, height, cell_size, mine_indices, offset_x,
                        offset_y, start_time, num_mines, flag, conn, cursor)
        if win:
            name = get_player_name(screen)
            if name:
                if (width, height, num_mines) == EASY_SIZE:
                    difficulty = "Легкий"
                elif (width, height, num_mines) == MEDIUM_SIZE:
                    difficulty = "Средний"
                elif (width, height, num_mines) == HARD_SIZE:
                    difficulty = "Сложный"
                else:
                     difficulty = "Пользовательский"

                save_record(cursor, conn, name, difficulty, elapsed_time)


def custom_game_settings(screen, conn, cursor):
    """Запускает меню пользовательских настроек."""
    pygame.init()
    font = pygame.font.Font(None, 30)
    input_boxes = {
        "Ширина": pygame.Rect(screen.get_width() // 2 - 100, screen.get_height() // 2 - 120, 200, 40),
        "Высота": pygame.Rect(screen.get_width() // 2 - 100, screen.get_height() // 2 - 60, 200, 40),
        "Кол-во мин": pygame.Rect(screen.get_width() // 2 - 100, screen.get_height() // 2, 200, 40)
    }

    text_inputs = {
        "Ширина": "",
        "Высота": "",
        "Кол-во мин": ""
    }

    active_box = None
    color_inactive = DARK_GRAY
    color_active = GRAY
    done = False

    back_button_rect = pygame.Rect(screen.get_width() // 2 - 60, screen.get_height() - 50, 120, 30)

    while not done:

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                if back_button_rect.collidepoint(event.pos) and event.button == 1:
                    return
                active_box = None
                for key, rect in input_boxes.items():
                    if rect.collidepoint(event.pos):
                        active_box = key
                        break
            if event.type == pygame.KEYDOWN:
                if active_box:
                    if event.key == pygame.K_RETURN:
                        try:
                            width = int(text_inputs["Ширина"]) if text_inputs["Ширина"] != "" else 0
                            height = int(text_inputs["Высота"]) if text_inputs["Высота"] != "" else 0
                            num_mines = int(text_inputs["Кол-во мин"]) if text_inputs["Кол-во мин"] != "" else 0
                            if 5 <= width <= 40 and 5 <= height <= 40 and 1 <= num_mines < width * height:
                                done = True
                                start_game(screen, conn, cursor, width, height, num_mines)
                            else:
                                print("Некорректные данные")
                                text_inputs = {
                                    "Ширина": "",
                                    "Высота": "",
                                    "Кол-во мин": ""
                                }
                        except ValueError:
                            print("Введите целые числа")
                            text_inputs = {
                                "Ширина": "",
                                "Высота": "",
                                "Кол-во мин": ""
                            }
                    elif event.key == pygame.K_BACKSPACE:
                        text_inputs[active_box] = text_inputs[active_box][:-1]
                    elif event.unicode.isdigit():
                        text_inputs[active_box] += event.unicode

        screen.fill(LIGHT_GRAY)

        # Надпись с инструкцией
        instruction_font = pygame.font.Font(None, 24)
        instruction_text  = "Кликните на поле ввода и введите цифры, затем нажмите 'Enter'\n" \
                           "Ширина и высота: от 5 до 40.\n" \
                           "Кол-во мин: от 1 до (ширина * высота - 1)."

        y_offset = screen.get_height() // 2 - 250
        for line in instruction_text.split('\n'):
            instruction_line = instruction_font.render(line, True, BLACK)
            instruction_rect = instruction_line.get_rect(center=(screen.get_width() // 2, y_offset))
            screen.blit(instruction_line, instruction_rect)
            y_offset += instruction_line.get_height()

        for key, rect in input_boxes.items():
            color = color_active if active_box == key else color_inactive
            txt_surface = font.render(text_inputs[key], True, BLACK)
            width = max(200, txt_surface.get_width() + 10)
            input_boxes[key].w = width
            pygame.draw.rect(screen, color, input_boxes[key], 2)
            screen.blit(txt_surface, (input_boxes[key].x + 5, input_boxes[key].y + 5))

            label_surface = font.render(key, True, BLACK)
            label_rect = label_surface.get_rect(bottom=input_boxes[key].top - 5, left=input_boxes[key].left)
            screen.blit(label_surface, label_rect)

        # Кнопка "Назад"
        button_width = 120
        button_height = 30
        button_x = screen.get_width() // 2 - button_width // 2
        button_y = screen.get_height() - button_height - 20
        draw_button(screen, "Назад", button_x, button_y, button_width, button_height, DARK_GRAY, COLORR, lambda: None,
                    False)
        pygame.display.flip()


if __name__ == "__main__":
    main_menu()