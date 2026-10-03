Для разработки используется PostgreSQL, запущенный в Docker:

```bash
docker run -d --name rbk_db_dev \
  -e POSTGRES_USER=rbk_user \
  -e POSTGRES_PASSWORD=rbk_password_dev \
  -e POSTGRES_DB=rbk_db \
  -p 5442:5432 \
  -v rbk_pgdata_dev:/var/lib/postgresql/data \
  postgres:16-alpine