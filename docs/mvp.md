# MVP

## Letter

Each letter stores:

- [ ] Auto-generated ID
- [ ] Recipient
- [ ] Country
- [ ] Date sent
- [ ] Status
- [ ] Date received (optional)
- [ ] Notes (optional)

### Statuses

- [ ] In transit
- [ ] Received
- [ ] Unknown

## Telegram bot

### Commands

- [x] `/start` — show the main menu
- [ ] `/help` — show available commands
- [ ] `/send` — register a new outgoing letter
- [ ] `/receive` — mark a letter as received
- [ ] `/sent` — list outgoing letters
- [ ] `/received` — list received letters

### Buttons

Main menu:

- [x] 📮 Отправить
- [x] 📬 Получить
- [x] 📚 Посмотреть почту

The buttons currently lead to placeholders. Letter flows and storage belong to
the next steps.

## Automatic

- [ ] Generate sequential letter IDs
- [ ] Calculate transit time after a delivery date is added

## Storage

SQLite database via SQLAlchemy and Alembic.
