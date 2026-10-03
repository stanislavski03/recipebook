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