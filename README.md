# Bookstore Inventory API

[![CI](https://github.com/Yondayler/bookstore-inventory-api/actions/workflows/ci.yml/badge.svg)](https://github.com/Yondayler/bookstore-inventory-api/actions/workflows/ci.yml)

API REST para la gestión del inventario de una cadena de librerías, con cálculo
del precio de venta sugerido a partir de tasas de cambio USD obtenidas en tiempo
real.

Prueba técnica — **Nextep Innovation** · FullStack Developer (Backend Focus).

| | |
|---|---|
| **Stack** | Python 3.12 · Django 4.2 · Django REST Framework 3.15 |
| **Base de datos** | PostgreSQL gestionado (Supabase) en producción · SQLite/Postgres en local |
| **Despliegue** | Render (contenedor Docker) |
| **API pública** | https://bookstore-inventory-api-qtgy.onrender.com |
| **Documentación interactiva** | https://bookstore-inventory-api-qtgy.onrender.com/api/docs (Swagger UI) |
| **Tests** | 72 tests con pytest, ejecutados sobre PostgreSQL en CI |

[![Swagger UI de la API desplegada](docs/swagger-ui.png)](https://bookstore-inventory-api-qtgy.onrender.com/api/docs)

<p align="center"><sub>Documentación OpenAPI 3 generada automáticamente y servida por la propia API</sub></p>

---

## Pruébala ahora mismo

Sin instalar nada. Copia y pega:

```bash
API=https://bookstore-inventory-api-qtgy.onrender.com

# 1. El servicio y su base de datos responden
curl $API/health

# 2. Inventario actual
curl "$API/books?page_size=3"

# 3. Crear un libro y quedarnos con su id
ID=$(curl -s -X POST $API/books -H "Content-Type: application/json" -d '{
  "title": "El Quijote",
  "author": "Miguel de Cervantes",
  "isbn": "9788420412146",
  "cost_usd": 15.99,
  "stock_quantity": 25,
  "category": "Literatura Clásica",
  "supplier_country": "ES"
}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

# 4. Precio de venta sugerido con la tasa USD→EUR de este momento
curl -X POST $API/books/$ID/calculate-price -H "Content-Type: application/json" -d '{}'

# 5. Reglas de negocio en acción: ISBN inválido → 400 con el detalle del campo
curl -X POST $API/books -H "Content-Type: application/json" \
  -d '{"title":"X","author":"Y","isbn":"123","cost_usd":10}'

# 6. Dejarlo como estaba
curl -X DELETE $API/books/$ID
```

Si repites el paso 3, la segunda vez responde `400`: ese ISBN ya existe y no se
permiten libros duplicados.

O importa la [colección de Postman](#7-colección-de-postman), que ya apunta a
esta URL, y ejecútala entera con el *Collection Runner*.

> La primera petición puede tardar ~50 s si el servicio estaba dormido: es el
> plan gratuito de Render. Las siguientes responden en ~150 ms.

---

## Índice

1. [Requisitos previos](#1-requisitos-previos)
2. [Ejecución local](#2-ejecución-local)
3. [Ejecución con Docker](#3-ejecución-con-docker)
4. [Endpoints y ejemplos de uso](#4-endpoints-y-ejemplos-de-uso)
5. [Reglas de negocio](#5-reglas-de-negocio)
6. [Manejo de errores](#6-manejo-de-errores)
7. [Colección de Postman](#7-colección-de-postman)
8. [Tests](#8-tests)
9. [Despliegue en Render + Supabase](#9-despliegue-en-render--supabase)
10. [Variables de entorno](#10-variables-de-entorno)
11. [Estructura del proyecto](#11-estructura-del-proyecto)
12. [Decisiones de diseño](#12-decisiones-de-diseño)

---

## 1. Requisitos previos

Para ejecutar el proyecto **con Docker** (recomendado, no necesitas Python):

- Docker 24+ y Docker Compose v2

Para ejecutarlo **sin Docker**:

- **Python 3.9 – 3.12** (Django 4.2 no soporta 3.13 todavía; la imagen de
  producción usa 3.12). Comprueba tu versión con `python3 --version`.
- `pip` y `venv`
- No hace falta base de datos: sin `DATABASE_URL` el proyecto usa SQLite
  automáticamente, lo que basta para desarrollo y para correr los tests.

---

## 2. Ejecución local

```bash
# 1. Clonar el repositorio
git clone https://github.com/Yondayler/bookstore-inventory-api.git
cd bookstore-inventory-api

# 2. Crear el entorno virtual e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Aplicar migraciones (crea el SQLite local)
python manage.py migrate

# 4. Cargar 6 libros de ejemplo
python manage.py seed_books

# 5. Arrancar el servidor
python manage.py runserver
```

Eso es todo: **no hay que configurar ninguna variable de entorno**. Si quieres
cambiar algo (moneda local, margen, proveedor de tasas…), copia la plantilla y
edítala — cada variable está explicada ahí mismo:

```bash
cp .env.example .env
```

La API queda disponible en **http://localhost:8000**:

- `http://localhost:8000/` → índice de endpoints
- `http://localhost:8000/api/docs` → Swagger UI
- `http://localhost:8000/health` → health check

```bash
curl http://localhost:8000/books
curl -X POST http://localhost:8000/books/1/calculate-price \
  -H "Content-Type: application/json" -d '{}'
```

Para usar PostgreSQL en local en lugar de SQLite basta con exportar la variable:

```bash
export DATABASE_URL="postgres://usuario:password@localhost:5432/bookstore"
export DB_SSL_REQUIRE=false
python manage.py migrate
```

---

## 3. Ejecución con Docker

El repositorio incluye `Dockerfile` y `docker-compose.yml`. Compose levanta la
API junto a un PostgreSQL 16, aplica las migraciones y carga los datos de
ejemplo automáticamente:

```bash
docker compose up --build
```

- API: http://localhost:8000
- PostgreSQL: `localhost:5432` (usuario/password/base: `bookstore`)

Para detenerlo y borrar los volúmenes:

```bash
docker compose down -v
```

Ejecutar solo la imagen de la API, apuntando a cualquier base de datos:

```bash
docker build -t bookstore-inventory-api .
docker run --rm -p 8000:8000 \
  -e SECRET_KEY="algo-secreto" \
  -e DATABASE_URL="postgresql://usuario:password@host:5432/postgres" \
  bookstore-inventory-api
```

El contenedor no depende de ninguna configuración local: todo se controla con
variables de entorno (ver [sección 10](#10-variables-de-entorno)).

---

## 4. Endpoints y ejemplos de uso

Base URL local: `http://localhost:8000` — producción: `https://bookstore-inventory-api-qtgy.onrender.com`.
Todas las rutas aceptan la barra final de forma opcional (`/books` y `/books/`).

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/books` | Crear libro |
| `GET` | `/books` | Listar libros (paginado + filtros) |
| `GET` | `/books/{id}` | Obtener libro por ID |
| `PUT` | `/books/{id}` | Actualizar libro (completo) |
| `PATCH` | `/books/{id}` | Actualizar libro (parcial) |
| `DELETE` | `/books/{id}` | Eliminar libro |
| `GET` | `/books/search?category={category}` | Buscar por categoría |
| `GET` | `/books/low-stock?threshold=10` | Libros con stock bajo |
| `POST` | `/books/{id}/calculate-price` | Calcular precio de venta sugerido |
| `GET` | `/health` | Estado del servicio y de la base de datos |
| `GET` | `/api/docs` · `/api/schema` | Swagger UI y esquema OpenAPI 3 |

### Crear libro

```bash
curl -X POST http://localhost:8000/books \
  -H "Content-Type: application/json" \
  -d '{
    "title": "El Quijote",
    "author": "Miguel de Cervantes",
    "isbn": "978-84-376-0494-7",
    "cost_usd": 15.99,
    "stock_quantity": 25,
    "category": "Literatura Clásica",
    "supplier_country": "ES"
  }'
```

`201 Created`

```json
{
  "id": 1,
  "title": "El Quijote",
  "author": "Miguel de Cervantes",
  "isbn": "978-84-376-0494-7",
  "cost_usd": 15.99,
  "selling_price_local": null,
  "stock_quantity": 25,
  "category": "Literatura Clásica",
  "supplier_country": "ES",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z",
  "selling_price_currency": "",
  "price_calculated_at": null
}
```

### Listar libros

```bash
curl "http://localhost:8000/books?page=1&page_size=10"
```

```json
{
  "count": 6,
  "total_pages": 1,
  "current_page": 1,
  "page_size": 10,
  "next": null,
  "previous": null,
  "results": [ { "id": 1, "title": "El Quijote", "...": "..." } ]
}
```

Filtros disponibles en el listado: `category`, `author`, `supplier_country`,
`q` (busca en título, autor e ISBN), `min_stock`, `max_stock` y `ordering`
(`title`, `cost_usd`, `stock_quantity`, `created_at`, … con `-` para invertir).

```bash
curl "http://localhost:8000/books?q=cervantes&ordering=-cost_usd"
```

### Obtener, actualizar y eliminar

```bash
curl http://localhost:8000/books/1

curl -X PUT http://localhost:8000/books/1 \
  -H "Content-Type: application/json" \
  -d '{"title":"Don Quijote de la Mancha","author":"Miguel de Cervantes","isbn":"978-84-376-0494-7","cost_usd":17.50,"stock_quantity":12,"category":"Literatura Clásica","supplier_country":"ES"}'

curl -X PATCH http://localhost:8000/books/1 \
  -H "Content-Type: application/json" -d '{"stock_quantity": 4}'

curl -X DELETE http://localhost:8000/books/1     # 204 No Content
```

### Buscar por categoría

```bash
curl "http://localhost:8000/books/search?category=Literatura"
```

Coincidencia parcial y sin distinguir mayúsculas. Si falta el parámetro
`category` la API responde `400`.

### Libros con stock bajo

```bash
curl "http://localhost:8000/books/low-stock?threshold=5"
```

```json
{
  "count": 2,
  "total_pages": 1,
  "current_page": 1,
  "page_size": 20,
  "next": null,
  "previous": null,
  "results": [ { "id": 4, "title": "La Sombra del Viento", "stock_quantity": 0, "...": "..." } ],
  "threshold": 5
}
```

### Calcular precio de venta sugerido

```bash
curl -X POST http://localhost:8000/books/1/calculate-price \
  -H "Content-Type: application/json" -d '{}'
```

`200 OK`

```json
{
  "book_id": 1,
  "cost_usd": 15.99,
  "exchange_rate": 0.85,
  "cost_local": 13.59,
  "margin_percentage": 40,
  "selling_price_local": 19.03,
  "currency": "EUR",
  "calculation_timestamp": "2025-01-15T10:30:00Z",
  "rate_source": "api",
  "rate_provider": "exchangerate-api.com",
  "fallback_used": false
}
```

> Los valores del ejemplo son los del enunciado. Al ejecutarlo verás otros:
> `exchange_rate` es la cotización real del momento, así que `cost_local` y
> `selling_price_local` varían con ella. Lo que no varía es la fórmula.

Lógica aplicada:

1. Se toma el `cost_usd` del libro.
2. Se consulta la tasa USD → moneda local en
   `https://api.exchangerate-api.com/v4/latest/USD` (respuesta cacheada 10
   minutos para no saturar al proveedor).
3. `cost_local = cost_usd × exchange_rate`.
4. `selling_price_local = cost_local × (1 + margen/100)` con un margen del **40 %**.
5. Se persiste `selling_price_local` (y la moneda y la fecha del cálculo) en la
   base de datos.
6. Se devuelve el cálculo detallado.

El cuerpo de la petición es opcional y admite dos ajustes:

```bash
curl -X POST http://localhost:8000/books/1/calculate-price \
  -H "Content-Type: application/json" \
  -d '{"currency": "MXN", "margin_percentage": 25}'
```

Los campos `rate_source` (`api` | `cache` | `fallback`) y `fallback_used`
indican de dónde salió la tasa, de modo que el cliente sabe si el precio se
calculó con datos en vivo o con la tasa por defecto.

---

## 5. Reglas de negocio

| Regla | Implementación |
|---|---|
| `cost_usd` debe ser mayor a 0 | Validación en el serializer + `CheckConstraint` en la base de datos |
| `stock_quantity` no puede ser negativo | `PositiveIntegerField` + `CheckConstraint` |
| `isbn` con formato válido (10 o 13 dígitos) | `books/validators.py`; acepta guiones y espacios, y la `X` final de un ISBN-10 |
| No permitir ISBN duplicados | Índice único sobre el ISBN normalizado: `978-84-376-0494-7` y `9788437604947` se detectan como el mismo libro |
| Si la API de cambio falla, usar tasa por defecto | `FALLBACK_EXCHANGE_RATES`; la respuesta marca `fallback_used: true` |
| Manejar errores 400, 404, 500, 503 | Handler de excepciones unificado (ver siguiente sección) |

La validación del **dígito de control** del ISBN está implementada pero
desactivada por defecto (la prueba solo pide validar el formato). Se activa con
`ISBN_VALIDATE_CHECKSUM=true`.

---

## 6. Manejo de errores

Todas las respuestas de error comparten el mismo formato:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request contains invalid data.",
    "details": { "isbn": ["ISBN must contain 10 or 13 digits, got 3: '123'."] }
  },
  "status_code": 400
}
```

| Código | Cuándo se produce |
|---|---|
| `400` | Datos inválidos, ISBN duplicado o mal formado, `cost_usd` ≤ 0, stock negativo, moneda inexistente, parámetros de consulta inválidos |
| `403` | Solo si `API_KEY` está configurada: escritura sin la cabecera `X-API-Key` correcta |
| `404` | El libro solicitado no existe, o la ruta no corresponde a ningún endpoint |
| `405` | Método HTTP no permitido en esa ruta |
| `500` | Error inesperado (se registra en los logs y nunca devuelve HTML) |
| `503` | El proveedor de tasas no responde **y** no hay tasa por defecto configurada para esa moneda |

Nota: si el proveedor de tasas falla pero sí existe una tasa por defecto, la
respuesta es `200` con `fallback_used: true`, tal y como pide la regla de
negocio.

---

## 7. Colección de Postman

En la carpeta [`postman/`](postman/) hay tres archivos para importar en Postman
(*File → Import*):

| Archivo | Contenido |
|---|---|
| `Bookstore-Inventory-API.postman_collection.json` | Todas las peticiones, agrupadas en carpetas (Health, CRUD, opcionales, cálculo de precio y casos de error) |
| `Bookstore-API-Production.postman_environment.json` | `base_url` apuntando a la API desplegada |
| `Bookstore-API-Local.postman_environment.json` | `base_url` apuntando a `http://localhost:8000` |

Selecciona el environment **Bookstore API - Production** y ya puedes ejecutar
todo contra la API pública, sin levantar nada en local. Cada petición lleva sus
propios tests, así que lo más cómodo es lanzar la colección entera con el
*Collection Runner*.

Está pensada para ejecutarse tantas veces como haga falta sobre un entorno
compartido: *Create book* genera un ISBN aleatorio (nunca choca con un libro
existente) y guarda su `id`; las peticiones que modifican o borran actúan solo
sobre ese libro y se detienen si no existe, de modo que los libros de ejemplo
quedan intactos.

Sin abrir Postman:

```bash
npx newman run postman/Bookstore-Inventory-API.postman_collection.json \
  -e postman/Bookstore-API-Production.postman_environment.json
# 20 peticiones · 33 assertions · 0 fallos
```

---

## 8. Tests

```bash
pip install -r requirements-dev.txt
pytest                     # 72 tests
pytest --cov=books --cov=core --cov-report=term-missing
```

La suite cubre el CRUD completo, la paginación y los filtros, cada regla de
negocio, el endpoint de cálculo de precio (incluida la aritmética exacta del
ejemplo de la prueba: 15.99 × 0.85 = 13.59 → +40 % = 19.03), el comportamiento
ante fallos del proveedor de tasas, la protección opcional por API key y la
forma del esquema OpenAPI. Las llamadas HTTP externas se simulan con
`responses`, de modo que los tests no dependen de la red.

### Integración continua

[GitHub Actions](.github/workflows/ci.yml) ejecuta en cada `push` la suite
contra un PostgreSQL real, y además construye la imagen, levanta el
`docker-compose.yml` entero y lanza la colección de Postman con newman contra
él. Así el `docker compose up` de este README y la colección entregada están
verificados, no solo escritos.

---

## 9. Despliegue en Render + Supabase

La API corre como **contenedor Docker en Render** y la base de datos es un
**PostgreSQL gestionado en Supabase**. Están separados a propósito: el plan
gratuito de Render suspende los servicios inactivos, y con la base de datos
fuera los datos no dependen de eso.

Al arrancar, el contenedor aplica las migraciones y levanta gunicorn; no hace
falta ningún paso manual tras el despliegue. El [`render.yaml`](render.yaml)
incluido reproduce el servicio completo como *blueprint*, y solo pide dos
variables: `DATABASE_URL` (la cadena de conexión de Supabase) y `SECRET_KEY`.

> El plan gratuito de Render duerme el servicio tras 15 minutos sin tráfico: la
> primera petición puede tardar ~50 s. Un workflow programado hace ping a
> `/health` para mantenerlo despierto. Los datos nunca se pierden, viven en
> Supabase.

---

## 10. Variables de entorno

**Ninguna es obligatoria**: sin configurar nada, el proyecto arranca con SQLite
y valores por defecto sensatos. Estas son las que cambian el comportamiento:

| Variable | Por defecto | Para qué sirve |
|---|---|---|
| `DATABASE_URL` | vacío → SQLite | Conexión PostgreSQL; es lo único imprescindible en producción |
| `SECRET_KEY` | clave de desarrollo | Clave de Django; obligatoria en producción |
| `DEBUG` | `false` | Modo depuración |
| `DEFAULT_LOCAL_CURRENCY` | `EUR` | Moneda local del cálculo de precios |
| `DEFAULT_MARGIN_PERCENTAGE` | `40` | Margen de ganancia |
| `FALLBACK_EXCHANGE_RATES` | JSON con 11 monedas | Tasas a usar si el proveedor falla |
| `API_KEY` | vacío → API abierta | Si se define, las escrituras exigen la cabecera `X-API-Key` |

El resto —ajustes de conexión, caché, seguridad HTTPS y arranque del
contenedor— está documentado con comentarios en [`.env.example`](.env.example).

Sobre `API_KEY`: el entorno desplegado está **abierto a propósito**, para que se
pueda probar cualquier endpoint sin configurar nada. Definir esa variable
convierte `POST`, `PUT`, `PATCH` y `DELETE` en operaciones con clave (`403` sin
ella) dejando las lecturas públicas.

---

## 11. Estructura del proyecto

```
bookstore-inventory-api/
├── config/                     # Proyecto Django
│   ├── settings.py             # Configuración por variables de entorno
│   ├── env.py                  # Lectura tipada de variables de entorno
│   └── urls.py                 # Rutas raíz (/, /health, /books, /api/docs)
├── core/                       # Utilidades transversales
│   ├── exception_handler.py    # Formato único de errores (400/403/404/500/503)
│   ├── permissions.py          # Candado opcional por API key en las escrituras
│   ├── pagination.py           # Paginación estándar
│   ├── schema.py               # Ajustes del esquema OpenAPI
│   └── views.py                # Índice de la API y health check
├── books/                      # Aplicación de dominio
│   ├── models.py               # Modelo Book + constraints
│   ├── serializers.py          # Validación de entrada/salida
│   ├── validators.py           # Validación y normalización de ISBN
│   ├── views.py                # ViewSet: CRUD, search, low-stock, calculate-price
│   ├── urls.py                 # Router (barra final opcional)
│   ├── exceptions.py           # Errores de dominio (503 / moneda no soportada)
│   ├── services/
│   │   ├── exchange_rate.py    # Cliente del proveedor de tasas + caché + fallback
│   │   └── pricing.py          # Cálculo del precio sugerido (Decimal)
│   ├── migrations/             # Esquema + tabla de caché compartida
│   ├── management/commands/
│   │   └── seed_books.py       # Datos de ejemplo
│   └── tests/                  # 72 tests
├── .github/workflows/          # CI (tests sobre Postgres + Docker) y keep-alive
├── postman/                    # Colección + environments (producción y local)
├── docs/                       # Capturas usadas en este README
├── scripts/entrypoint.sh       # Migraciones + gunicorn
├── Dockerfile
├── docker-compose.yml
├── render.yaml                 # Blueprint de despliegue en Render
├── requirements.txt
└── requirements-dev.txt
```

---

## 12. Decisiones de diseño

- **Separación en capas.** Las vistas solo orquestan; la integración externa
  (`services/exchange_rate.py`) y el cálculo de precios
  (`services/pricing.py`) viven en servicios independientes, testeables sin
  HTTP y reutilizables desde un comando o una tarea programada.
- **`Decimal` en todo el flujo de dinero**, con redondeo *half-up* a dos
  decimales solo al final. Con `float` el ejemplo de la prueba ya arrastraría
  error de coma flotante.
- **Caché de las tasas de cambio** (10 minutos). Un endpoint que llama a un
  tercero en cada petición es frágil y lento; además, el fallback configurable
  evita que una caída del proveedor deje la operación bloqueada. La caché vive
  **en la base de datos**, no en memoria: gunicorn levanta varios procesos y una
  caché en memoria sería privada de cada uno, así que la misma tasa se pediría
  una vez por worker.
- **ISBN normalizado en una columna aparte.** Permite guardar el ISBN tal y
  como lo escribe el usuario y, a la vez, garantizar la unicidad real
  independientemente de los guiones.
- **`selling_price_local` es de solo lectura** en el CRUD: solo lo escribe el
  endpoint de cálculo, de modo que el precio nunca puede contradecir a la tasa
  con la que se obtuvo.
- **Validación duplicada en serializer y base de datos.** El serializer
  devuelve errores 400 claros; los `CheckConstraint` garantizan la integridad
  aunque alguien escriba en la base de datos por otra vía.
- **Barra final opcional en las rutas.** Django redirige `/books` a `/books/`
  con un 301 que puede perder el cuerpo de un POST; el router acepta ambas
  formas para evitarlo.
- **Errores con un formato único** y sin HTML, para que cualquier cliente
  (Postman, front-end, otro servicio) pueda tratarlos de forma programática, con
  mensajes que nombran el recurso (`Book with id 4242 was not found.`) en lugar
  del texto genérico del framework.
- **Campos añadidos sobre el modelo del enunciado.** El libro incluye
  `selling_price_currency` y `price_calculated_at`, y el cálculo devuelve
  `rate_source`, `rate_provider` y `fallback_used`. Son aditivos —el JSON del
  enunciado sigue estando completo— y responden a una pregunta que el
  enunciado deja abierta: un precio guardado sin su moneda ni su fecha no es
  auditable, y un cliente necesita saber si el precio se calculó con la tasa en
  vivo o con la de respaldo.
