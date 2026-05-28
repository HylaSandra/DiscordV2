# DiscordV2

DiscordV2 to aplikacja komunikacyjna w Django inspirowana Discordem. Projekt zawiera:

- rejestrację, logowanie, profile i avatary,
- role `Administrator`, `Moderator`, `Użytkownik`,
- kanały tekstowe publiczne, grupowe i głosowe,
- wiadomości prywatne,
- wiadomości tekstowe, obrazki i nagrania głosowe,
- edytowanie i usuwanie wiadomości oraz reakcje,
- moderację użytkowników,
- wyszukiwarkę, status online/offline i powiadomienia.

## Uruchomienie lokalne

1. Utwórz i aktywuj środowisko wirtualne.
2. Zainstaluj zależności:

```bash
pip install -r requirements.txt
```

3. Ustaw zmienne środowiskowe, np. na podstawie `.env.example`.
4. Wykonaj migracje:

```bash
python manage.py makemigrations
python manage.py migrate
```

5. Utwórz konto administratora:

```bash
python manage.py createsuperuser
```

6. Uruchom serwer:

```bash
python manage.py runserver
```

## Zmienne środowiskowe

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`
- `REDIS_URL`
- `TIME_ZONE`

## Wdrożenie na Render

Projekt zawiera pliki `build.sh` i `render.yaml`.

