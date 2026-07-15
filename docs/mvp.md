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

The Send flow is complete. Receive and Journal still lead to placeholders.

### Send flow

- [x] Choose an existing recipient or add a new one
- [x] Use today's date or enter another date
- [x] Review and confirm the record
- [x] Cancel from any button-driven step
- [x] Save outgoing mail with the In transit status

## Automatic

- [ ] Generate sequential letter IDs
- [ ] Calculate transit time after a delivery date is added

## Storage

PostgreSQL database via SQLAlchemy and Alembic.
