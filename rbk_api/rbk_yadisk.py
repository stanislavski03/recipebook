"""Yandex.Disk integration for RecipeBook.

Работаем через REST API: https://yandex.ru/dev/disk/api/reference/
Авторизация — OAuth-токен из переменной окружения RBK_YADISK_TOKEN.
"""
import os
import requests

_BASE = "https://cloud-api.yandex.net/v1/disk"
_TOKEN = os.getenv("RBK_YADISK_TOKEN", "")


def _headers() -> dict:
    if not _TOKEN:
        raise RuntimeError(
            "RBK_YADISK_TOKEN не задан. Добавь его в .env или в environment контейнера."
        )
    return {"Authorization": f"OAuth {_TOKEN}"}


# --- Информация о диске ---
def get_disk_info() -> dict:
    """Общая информация: занято, свободно, всего."""
    r = requests.get(f"{_BASE}/", headers=_headers(), timeout=10)
    r.raise_for_status()
    data = r.json()
    return {
        "total_space": data.get("total_space"),
        "used_space": data.get("used_space"),
        "free_space": data.get("total_space", 0) - data.get("used_space", 0),
        "user": data.get("user", {}).get("display_name"),
    }


# --- Список файлов ---
def list_files(path: str = "/") -> list:
    """Список файлов и папок в указанной директории."""
    r = requests.get(
        f"{_BASE}/resources",
        headers=_headers(),
        params={"path": path, "limit": 100},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    items = data.get("_embedded", {}).get("items", [])
    return [
        {
            "name": it["name"],
            "path": it["path"],
            "type": it["type"],  # "file" или "dir"
            "size": it.get("size"),
            "modified": it.get("modified"),
        }
        for it in items
    ]


# --- Папки ---
def create_folder(path: str) -> dict:
    """Создать папку. Если уже есть — Яндекс вернёт 409, игнорируем."""
    r = requests.put(
        f"{_BASE}/resources",
        headers=_headers(),
        params={"path": path},
        timeout=10,
    )
    if r.status_code == 409:
        return {"path": path, "status": "already_exists"}
    r.raise_for_status()
    return {"path": path, "status": "created"}


# --- Загрузка файла ---
def upload_file(local_path: str, remote_path: str, overwrite: bool = True) -> dict:
    """Загрузить файл на Яндекс-Диск.

    Двухшаговая схема:
      1. GET /resources/upload — получаем ссылку на загрузку.
      2. PUT на эту ссылку — отправляем файл.
    """
    # Шаг 1: получаем URL для загрузки
    r = requests.get(
        f"{_BASE}/resources/upload",
        headers=_headers(),
        params={"path": remote_path, "overwrite": str(overwrite).lower()},
        timeout=10,
    )
    r.raise_for_status()
    upload_url = r.json()["href"]

    # Шаг 2: заливаем файл
    with open(local_path, "rb") as f:
        put = requests.put(upload_url, files={"file": f}, timeout=60)
    put.raise_for_status()
    return {"path": remote_path, "status": "uploaded"}


# --- Скачивание ---
def download_file(remote_path: str, local_path: str) -> None:
    """Скачать файл с Яндекс-Диска."""
    r = requests.get(
        f"{_BASE}/resources/download",
        headers=_headers(),
        params={"path": remote_path},
        timeout=10,
    )
    r.raise_for_status()
    download_url = r.json()["href"]

    with requests.get(download_url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)


# --- Публичная ссылка ---
def publish(path: str) -> str:
    """Сделать файл публичным и получить ссылку."""
    r = requests.put(
        f"{_BASE}/resources/publish",
        headers=_headers(),
        params={"path": path},
        timeout=10,
    )
    r.raise_for_status()

    # Получаем мета-инфу — там будет public_url
    meta = requests.get(
        f"{_BASE}/resources",
        headers=_headers(),
        params={"path": path, "fields": "public_url"},
        timeout=10,
    )
    meta.raise_for_status()
    return meta.json().get("public_url", "")


# --- Удаление ---
def delete_file(path: str) -> None:
    """Удалить файл или папку (в корзину)."""
    r = requests.delete(
        f"{_BASE}/resources",
        headers=_headers(),
        params={"path": path, "permanently": "false"},
        timeout=10,
    )
    r.raise_for_status()


# --- Проверка существования ---
def exists(path: str) -> bool:
    """Проверить, существует ли файл/папка по пути."""
    r = requests.get(
        f"{_BASE}/resources",
        headers=_headers(),
        params={"path": path},
        timeout=10,
    )
    return r.status_code == 200