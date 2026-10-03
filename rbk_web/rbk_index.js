const form = document.getElementById("rbk-form");
const list = document.getElementById("rbk-recipes");

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = {
        title: form.title.value,
        author: form.author.value || "anonymous",
        description: form.description.value,
    };
    const resp = await fetch("/api/recipes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    if (resp.ok) {
        window.location.reload();
    } else {
        alert("Ошибка при добавлении рецепта");
    }
});