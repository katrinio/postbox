# MVP

## Letter

Each letter stores:

- [x] Auto-generated ID
- [x] Correspondent and direction
- [ ] Country
- [x] Date sent (optional for incoming mail)
- [x] Derived status
- [x] Date received (optional for outgoing mail)
- [x] Optional notes

### Statuses

- [x] In transit
- [x] Received

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

The Send, Receive, and Journal flows are complete.

### Send flow

- [x] Choose an existing recipient or add a new one
- [x] Use today's date or enter another date
- [x] Review and confirm the record
- [x] Cancel from any button-driven step
- [x] Save outgoing mail with the In transit status

### Receive flow

- [x] Choose an existing sender or add a new one
- [x] Use today's received date or enter another date
- [x] Keep the sent date unknown or enter a readable postmark date
- [x] Reject a sent date later than the received date
- [x] Review, confirm, or cancel the record
- [x] Save incoming mail with the Received status

### Journal

- [x] Show In transit, Outgoing, Incoming, and All filters
- [x] Order records by their mail event date
- [x] Paginate long lists
- [x] Open a detailed mail card
- [x] Show current transit time for outgoing mail
- [x] Keep every query scoped to the Telegram user

### Delivery

- [x] Show the delivery action only for outgoing mail that is still in transit
- [x] Use today's received date or enter another date
- [x] Reject a received date earlier than sending or later than today
- [x] Review, change, confirm, or cancel the delivery
- [x] Update the status and show the completed travel time

### Notes

- [x] Add a note from any mail card
- [x] Show multiline notes safely in Telegram HTML
- [x] Change or remove an existing note
- [x] Confirm changes and protect every action by the Telegram owner

## Automatic

- [ ] Generate sequential letter IDs
- [x] Calculate transit time after a delivery date is added

## Storage

PostgreSQL database via SQLAlchemy and Alembic.
