"""Dropbox integration for RecipeBook.

Все операции идут через официальный SDK dropbox>=12.
Токен берётся из переменной окружения RBK_DROPBOX_TOKEN.
"""
import os
import dropbox
from dropbox.exceptions import ApiError
from dropbox.files import WriteMode

_TOKEN = os.getenv("RBK_DROPBOX_TOKEN", "")


def _client() -> dropbox.Dropbox:
    """Создаёт Dropbox-клиент. Если токена нет — бросает понятную ошибку."""
    if not _TOKEN:
        raise RuntimeError(
            "RBK_DROPBOX_TOKEN не задан. Добавь его в .env или в environment контейнера."
        )
    return dropbox.Dropbox(_TOKEN)


def get_user_info() -> dict:
    """Информация об аккаунте: имя, email, тип."""
    dbx = _client()
    acc = dbx.users_get_current_account()
    return {
        "name": acc.name.display_name,
        "email": acc.email,
        "account_type": acc.account_type._tag,
    }


def get_space_usage() -> dict:
    """Сколько занято и свободно (в байтах)."""
    dbx = _client()
    usage = dbx.users_get_space_usage()
    allocated = usage.allocation.get_individual().allocated
    used = usage.used
    return {
        "allocated": allocated,
        "used": used,
        "free": allocated - used,
    }


def list_folder(path: str = "") -> list:
    """Список файлов и папок в указанной директории."""
    dbx = _client()
    result = dbx.files_list_folder(path)
    return [
        {
            "name": entry.name,
            "path": entry.path_display,
            "type": "folder" if entry.__class__.__name__ == "FolderMetadata" else "file",
        }
        for entry in result.entries
    ]


def create_folder(path: str) -> dict:
    """Создать папку по пути."""
    dbx = _client()
    try:
        result = dbx.files_create_folder_v2(path)
        meta = getattr(result, "metadata", result)
        return {"path": meta.path_display, "name": meta.name}
    except ApiError as e:
        raise RuntimeError(f"Не удалось создать папку: {e}")


def upload_file(local_path: str, remote_path: str) -> dict:
    """Загрузить файл в Dropbox. Если файл есть — перезаписать."""
    dbx = _client()
    with open(local_path, "rb") as f:
        result = dbx.files_upload(
            f.read(),
            remote_path,
            mode=WriteMode.overwrite,
        )
    # В новых версиях SDK возвращается сразу FileMetadata.
    # В старых — обёртка с полем .metadata. Обрабатываем оба случая.
    meta = getattr(result, "metadata", result)
    return {"path": meta.path_display, "size": meta.size}


def create_shared_link(remote_path: str) -> str:
    """Публичная ссылка на файл/папку."""
    dbx = _client()
    try:
        link = dbx.sharing_create_shared_link_with_settings(remote_path)
        return link.url
    except ApiError as e:
        # Если ссылка уже создана ранее — Dropbox вернёт ошибку.
        # Попробуем получить список и найти подходящую.
        links = dbx.sharing_list_shared_links(path=remote_path).links
        if links:
            return links[0].url
        raise RuntimeError(f"Не удалось создать ссылку: {e}")


def search_files(query: str) -> list:
    """Поиск по именам файлов."""
    dbx = _client()
    result = dbx.files_search_v2(query)
    out = []
    for m in result.matches:
        if hasattr(m, "metadata") and hasattr(m.metadata, "metadata"):
            md = m.metadata.metadata
            out.append({"name": md.name, "path": md.path_display})
    return out