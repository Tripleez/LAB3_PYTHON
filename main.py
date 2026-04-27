from PIL import Image
import os
import sys
import re


def load_keys(key_file):
    #Загружает ключи из файла.
    #Формат: (x, y) или x, y в каждой строке

    keys = []

    if not os.path.exists(key_file):
        print(f"Ошибка: файл {key_file} не существует!")
        return keys

    try:
        with open(key_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                # Убираем скобки и пробелы
                line = line.replace('(', '').replace(')', '').strip()

                # Ищем два числа (координаты)
                match = re.findall(r'-?\d+', line)
                if len(match) >= 2:
                    x = int(match[0])
                    y = int(match[1])
                    keys.append((x, y))
                else:
                    print(f"Предупреждение: строка {line_num} не содержит двух чисел: {line}")

    except Exception as e:
        print(f"Ошибка при чтении файла ключей: {e}")

    return keys


def decode_text_from_image(image_path, keys, method):
    #Декодирует текст из изображения по заданным ключам и методу.
    #Для варианта 29: b0-G и b0-B (берём по 2 бита на пиксель)

    if not keys:
        print("Ошибка: нет ключей для декодирования!")
        return ""

    img = Image.open(image_path)
    pixels = img.load()
    width, height = img.size

    print(f"\n Размер изображения: {width}x{height}")
    print(f" Количество ключей: {len(keys)}")
    print(f" Первые 5 ключей: {keys[:5]}")

    bits = []

    for idx, (x, y) in enumerate(keys):
        if x >= width or y >= height:
            print(f"Предупреждение: ключ ({x}, {y}) выходит за пределы изображения")
            continue

        pixel = pixels[x, y]
        if len(pixel) >= 3:
            r, g, b = pixel[0], pixel[1], pixel[2]
        else:
            print(f"Ошибка: неожиданный формат пикселя {pixel}")
            continue

        # Для варианта 29: берём b0 из G и b0 из B
        if method == "b0-G,b0-B":
            bit_g = g & 1   # младший бит зелёного
            bit_b = b & 1   # младший бит синего
            bits.append(bit_g)
            bits.append(bit_b)

            # Показываем первые несколько пикселей для отладки
            if idx < 5:
                print(f"  Пиксель {idx}: ({x},{y}) R={r}, G={g}, B={b} -> биты: G0={bit_g}, B0={bit_b}")

    print(f"\n Собрано битов: {len(bits)}")

    # Преобразуем биты в байты
    byte_values = []
    for i in range(0, len(bits), 8):
        byte_bits = bits[i:i+8]
        if len(byte_bits) < 8:
            print(f" Неполный байт в конце: {byte_bits}")
            break
        byte_val = 0
        for j, bit in enumerate(byte_bits):
            byte_val |= (bit << (7 - j))
        byte_values.append(byte_val)

    print(f"Получено байтов: {len(byte_values)}")
    if byte_values:
        print(f"Первые 10 байтов: {byte_values[:10]}")

    # Пытаемся декодировать как UTF-8
    try:
        # Находим позицию нулевого байта (если есть)
        if 0 in byte_values:
            null_pos = byte_values.index(0)
            byte_values = byte_values[:null_pos]

        # Декодируем байты в строку UTF-8
        decoded_text = bytes(byte_values).decode('utf-8', errors='replace')
        return decoded_text
    except Exception as e:
        print(f"Ошибка декодирования: {e}")
        # Если не получилось, показываем как есть
        result = ""
        for bv in byte_values:
            if bv == 0:
                break
            if 32 <= bv <= 126:
                result += chr(bv)
            else:
                result += f'\\x{bv:02x}'
        return result


def encode_text_into_image(image_path, output_image_path, keys, text, method):
    #Кодирует текст в изображение по заданным ключам и методу.
    #Для варианта 29: b0-G, b0-B (по 2 бита на пиксель).

    if not keys:
        print("Ошибка: нет ключей для кодирования!")
        return False

    img = Image.open(image_path).copy()
    pixels = img.load()
    width, height = img.size

    # Преобразуем текст в байты UTF-8
    text_bytes = text.encode('utf-8')
    # Добавляем нулевой байт для обозначения конца
    text_bytes += b'\x00'

    bits_to_encode = []
    for byte_val in text_bytes:
        for i in range(7, -1, -1):  # старший бит первым
            bits_to_encode.append((byte_val >> i) & 1)

    print(f"\nТекст: {text}")
    print(f"Байты UTF-8: {list(text_bytes)}")
    print(f"Длина текста: {len(text)} символов, {len(text_bytes)} байт (с NULL)")
    print(f"Всего битов для кодирования: {len(bits_to_encode)}")
    print(f"Доступно битов в ключах: {len(keys) * 2}")

    if len(bits_to_encode) > len(keys) * 2:
        print("Ошибка: текст слишком длинный для данного количества ключей.")
        print(f"Нужно битов: {len(bits_to_encode)}, доступно: {len(keys) * 2}")
        return False

    # Вывод информации для первого символа (как требуется в задании)
    if text_bytes:
        first_char = text_bytes[0]
        print("\n" + "=" * 50)
        print("КОДИРОВАНИЕ ПЕРВОГО СИМВОЛА")
        print("=" * 50)
        print(f"Первый байт: {first_char} (0x{first_char:02x})")
        print(f"Это часть символа: первый байт UTF-8 для '{text[0]}'")
        # Биты первого байта
        first_char_bits = [(first_char >> i) & 1 for i in range(7, -1, -1)]
        print(f"Биты первого байта (b7 b6 b5 b4 b3 b2 b1 b0): {first_char_bits}")

    bit_index = 0
    encoded_keys_used = 0
    first_pixel_shown = False

    for idx, (x, y) in enumerate(keys):
        if bit_index >= len(bits_to_encode):
            break

        if x >= width or y >= height:
            print(f"Предупреждение: ключ ({x}, {y}) выходит за пределы")
            continue

        pixel = list(pixels[x, y])
        if len(pixel) >= 3:
            original_r, original_g, original_b = pixel[0], pixel[1], pixel[2]
        else:
            continue

        # Показываем первые 2 пикселя для первого символа
        if not first_pixel_shown and idx < 2:
            print("\n" + "-" * 40)
            print(f"Пиксель для битов первого байта (позиция {idx}):")
            print(f"  Координаты: ({x}, {y})")
            print(f"  Исходные значения: R={original_r}, G={original_g}, B={original_b}")

        # Кодируем 2 бита (b0-G, b0-B)
        if bit_index + 1 < len(bits_to_encode):
            bit_g = bits_to_encode[bit_index]
            bit_b = bits_to_encode[bit_index + 1]
        else:
            break

        #Изменяем младший бит зелёного и синего
        new_g = (original_g & ~1) | bit_g
        new_b = (original_b & ~1) | bit_b
        pixel[1] = new_g
        pixel[2] = new_b
        pixels[x, y] = tuple(pixel)

        #Показываем изменённые значения
        if not first_pixel_shown and idx < 2:
            print(f"  Закодированные биты: G0={bit_g}, B0={bit_b}")
            print(f"  Новые значения: R={pixel[0]}, G={new_g}, B={new_b}")
            if idx == 1:
                first_pixel_shown = True
                print("-" * 40)

        bit_index += 2
        encoded_keys_used += 1

    #Сохраняем закодированное изображение
    img.save(output_image_path)
    print(f"\nИзображение сохранено как {output_image_path}")
    print(f"Закодировано {bit_index} бит, использовано {encoded_keys_used} ключей из {len(keys)}")
    return True


def decode_and_display(image_path, keys, method, title="Декодированное сообщение"):
    #Декодирует и красиво выводит сообщение
    decoded = decode_text_from_image(image_path, keys, method)
    print(f"\n{'='*50}")
    print(title)
    print(f"{'='*50}")
    print(decoded)
    print(f"{'='*50}")
    return decoded


def main():
    # 29 вариант
    variant = 29
    encoded_image = "new29.png"
    key_file = "keys29.txt"
    method = "b0-G,b0-B"

    print("=" * 60)
    print(f"Лабораторная работа №3. Стеганография. Вариант {variant}")
    print(f"Метод кодирования: {method}")
    print("=" * 60)

    #Проверка наличия файлов
    if not os.path.exists(encoded_image):
        print(f"\nФайл {encoded_image} не найден!")
        print("Убедитесь, что файл находится в той же папке, что и программа.")
        sys.exit(1)

    if not os.path.exists(key_file):
        print(f"\nФайл {key_file} не найден!")
        sys.exit(1)

    #Загрузка ключей
    keys = load_keys(key_file)
    print(f"\nЗагружено ключей (координат пикселей): {len(keys)}")

    if len(keys) == 0:
        print("\nОШИБКА: Не удалось загрузить ключи из файла!")
        sys.exit(1)

    #Декодирование текста из закодированного изображения
    print("\n" + "-" * 40)
    print("ДЕКОДИРОВАНИЕ текста из закодированного изображения")
    print("-" * 40)

    original_message = decode_and_display(encoded_image, keys, method, "Исходное закодированное сообщение")

    #Кодирование нового текста в изображение
    print("\n" + "-" * 40)
    print("КОДИРОВАНИЕ нового текста в изображение")
    print("-" * 40)

    new_text = input("\nВведите текст для кодирования: ").strip()
    if not new_text:
        # Пример сообщения из исходного декодированного текста

        if original_message and len(original_message) > 0:
            new_text = original_message
            print(f"Используется исходное сообщение: \"{new_text}\"")

    output_image = "new29.png"
    success = encode_text_into_image(encoded_image, output_image, keys, new_text, method)

    if success:
        print("\n" + "-" * 40)
        print("ПРОВЕРКА корректности кодирования")
        print("-" * 40)

        decoded_new = decode_and_display(output_image, keys, method, "Декодированный текст из нового изображения")

        print(f"\n{'='*50}")
        print("СРАВНЕНИЕ")
        print(f"{'='*50}")
        print(f"Исходный текст для кодирования: {new_text}")
        print(f"Декодированный текст:          {decoded_new}")

        if decoded_new == new_text:
            print("\nКодирование и декодирование выполнены корректно!")
        else:
            print("\nОШИБКА: Декодированный текст не совпадает с исходным.")

    else:
        print("\nОшибка при кодировании.")


if __name__ == "__main__":
    main()