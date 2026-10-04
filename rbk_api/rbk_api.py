from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rbk_config import RBK_WEB_DIR
from rbk_db import init_db, get_session, RbkRecipe

# --- Инициализация ---
app = FastAPI(title="RecipeBook API", version="0.1.0")
templates = Jinja2Templates(directory=str(RBK_WEB_DIR))
app.mount("/static", StaticFiles(directory=str(RBK_WEB_DIR)), name="static")

# Создаём таблицы при старте (для SQLite это ок; позже заменим на Alembic)
init_db()


# --- Pydantic-схемы ---
class RecipeIn(BaseModel):
    title: str
    description: str = ""
    author: str = "anonymous"


class RecipeOut(BaseModel):
    id: int
    title: str
    description: str
    author: str
    created_at: str | None = None


# --- API ---
@app.get("/health")
def health():
    return {"status": "ok", "service": "recipebook"}


@app.get("/api/recipes", response_model=list[RecipeOut])
def list_recipes(db: Session = Depends(get_session)):
    recipes = db.query(RbkRecipe).order_by(RbkRecipe.created_at.desc()).all()
    return [r.to_dict() for r in recipes]


@app.get("/api/recipes/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: int, db: Session = Depends(get_session)):
    recipe = db.get(RbkRecipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe.to_dict()


@app.post("/api/recipes", response_model=RecipeOut, status_code=201)
def create_recipe(payload: RecipeIn, db: Session = Depends(get_session)):
    recipe = RbkRecipe(
        title=payload.title,
        description=payload.description,
        author=payload.author,
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe.to_dict()


@app.delete("/api/recipes/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, db: Session = Depends(get_session)):
    recipe = db.get(RbkRecipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    db.delete(recipe)
    db.commit()
    return None


# --- HTML-страницы (пока заглушки, наполним на следующем шаге) ---
@app.get("/", response_class=HTMLResponse)
def page_index(request: Request, db: Session = Depends(get_session)):
    recipes = db.query(RbkRecipe).order_by(RbkRecipe.created_at.desc()).all()
    return templates.TemplateResponse(
        name="rbk_index.html",
        request=request,
        context={"recipes": [r.to_dict() for r in recipes]},
    )   

@app.get("/recipe/{recipe_id}", response_class=HTMLResponse)
def page_recipe(recipe_id: int, request: Request, db: Session = Depends(get_session)):
    recipe = db.get(RbkRecipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return templates.TemplateResponse(
        name="rbk_recipe.html",
        request=request,
        context={"recipe": recipe.to_dict()},
    )

# ============================================================================
# Dropbox integration
# ============================================================================
from rbk_dropbox import (
    get_user_info,
    get_space_usage,
    list_folder,
    upload_file,
    create_shared_link,
    search_files,
    create_folder,
)


@app.get("/api/dropbox/info")
def dropbox_info():
    return get_user_info()


@app.get("/api/dropbox/space")
def dropbox_space():
    return get_space_usage()


@app.get("/api/dropbox/list")
def dropbox_list(path: str = ""):
    return list_folder(path)


@app.get("/api/dropbox/search")
def dropbox_search(q: str):
    return search_files(q)


@app.post("/api/dropbox/export-recipes")
def dropbox_export_recipes(db: Session = Depends(get_session)):
    """Экспортирует все рецепты в JSON и загружает в Dropbox."""
    import json
    import tempfile
    from datetime import datetime
    from pathlib import Path

    recipes = db.query(RbkRecipe).all()
    data = [r.to_dict() for r in recipes]

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name

    try:
        # Создаём папку (если уже есть — просто игнорируем ошибку)
        try:
            create_folder("/rbk_exports")
        except RuntimeError:
            pass

        filename = f"/rbk_exports/recipes_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        upload_file(tmp_path, filename)
        link = create_shared_link(filename)
        return {
            "status": "ok",
            "path": filename,
            "link": link,
            "count": len(data),
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)

# ============================================================================
# Yandex.Disk integration
# ============================================================================
from rbk_yadisk import (
    get_disk_info,
    list_files as yadisk_list_files,
    create_folder as yadisk_create_folder,
    upload_file as yadisk_upload_file,
    publish as yadisk_publish,
    delete_file as yadisk_delete_file,
)


@app.get("/api/yadisk/info")
def yadisk_info():
    return get_disk_info()


@app.get("/api/yadisk/list")
def yadisk_list(path: str = "/"):
    return yadisk_list_files(path)


@app.post("/api/yadisk/backup")
def yadisk_backup(db: Session = Depends(get_session)):
    """Экспортирует рецепты в JSON и заливает на Яндекс-Диск."""
    import json
    import tempfile
    from datetime import datetime
    from pathlib import Path

    recipes = db.query(RbkRecipe).all()
    data = [r.to_dict() for r in recipes]

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name

    try:
        # Создаём папку (409 уже обрабатывается внутри)
        yadisk_create_folder("/rbk_backups")

        filename = f"/rbk_backups/recipes_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        yadisk_upload_file(tmp_path, filename)
        public_url = yadisk_publish(filename)

        return {
            "status": "ok",
            "path": filename,
            "public_url": public_url,
            "count": len(data),
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.get("/api/yadisk/find")
def yadisk_find():
    """Показать содержимое /rbk_backups (или вернуть пустой список)."""
    try:
        return yadisk_list_files("/rbk_backups")
    except Exception:
        return []