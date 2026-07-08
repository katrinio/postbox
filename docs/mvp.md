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

- [ ] `/help` — show available commands
- [ ] `/send` — register a new outgoing letter
- [ ] `/receive` — mark a letter as received
- [ ] `/sent` — list outgoing letters
- [ ] `/received` — list received letters

### Buttons

Main menu:

- [ ] 📮 Send letter
- [ ] 📬 Letter received
- [ ] 📤 Sent letters
- [ ] 📥 Received letters
- [ ] ❓ Help

## Automatic

- [ ] Generate sequential letter IDs
- [ ] Calculate transit time after a delivery date is added

## Storage

SQLite database via SQLAlchemy and Alembic.
