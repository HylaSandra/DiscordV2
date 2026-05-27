# DiscordV2

DiscordV2 to aplikacja komunikacyjna w Django inspirowana Discordem. Projekt zawiera:

- rejestrację, logowanie, profile i avatary,
- role `Administrator`, `Moderator`, `Użytkownik`,
- kanały tekstowe publiczne, grupowe i głosowe,
- wiadomości prywatne 1:1,
- wiadomości tekstowe, obrazki i nagrania głosowe,
- edytowanie, usuwanie oraz reakcje emoji,
- moderację użytkowników,
- wyszukiwarkę, status online/offline i powiadomienia,
- konfigurację gotową pod wdrożenie na Render.

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

Po połączeniu repozytorium z Render:

1. utwórz usługę Web Service,
2. podłącz bazę PostgreSQL,
3. podłącz Redis/Key Value dla websocketów,
4. ustaw start przez ASGI (`config.asgi:application`),
5. po wdrożeniu utwórz superusera w Render Shell.

Jeżeli korzystasz z darmowych planów Render, pamiętaj, że darmowa baza Postgres ma ograniczenia i według aktualnej dokumentacji może wygasnąć po 30 dniach.

## Uwaga

W tym środowisku roboczym nie było dostępnego interpretera Pythona, więc projekt został przygotowany ręcznie i nie został tutaj uruchomiony. Przed oddaniem pracy warto lokalnie wykonać `makemigrations`, `migrate` i test przejścia przez główne scenariusze.

Skrypt `build.sh` wykonuje `makemigrations` przed `migrate`, aby pierwsze wdrożenie zadziałało nawet wtedy, gdy migracje nie zostały wcześniej wygenerowane lokalnie. Do normalnej dalszej pracy nadal najlepiej jest wygenerować i zatwierdzić migracje we własnym repozytorium.
