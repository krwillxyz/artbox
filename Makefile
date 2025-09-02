APP_DIR=/opt/artbox/uploader
VENV=/opt/artbox/venv
ENVFILE=/etc/artbox/uploader.env
SERVICE=art-upload

.PHONY: all install venv deps configure start stop restart status logs dev pull update

all: install

install: venv deps configure
	@echo "Copying app to $(APP_DIR)"
	sudo mkdir -p $(APP_DIR)/app/templates $(APP_DIR)/app/static
	sudo rsync -a uploader/app/ $(APP_DIR)/app/
	@echo "Installing systemd service"
	sudo mkdir -p /etc/artbox
	sudo cp deploy/$(SERVICE).service /etc/systemd/system/$(SERVICE).service
	sudo systemctl daemon-reload
	sudo systemctl enable --now $(SERVICE)
	@echo "Done."

venv:
	sudo mkdir -p $(VENV)
	sudo test -x $(VENV)/bin/python || sudo python3 -m venv $(VENV)

deps:
	sudo $(VENV)/bin/pip install -r uploader/requirements.txt

configure:
	@if [ ! -f $(ENVFILE) ]; then \
	  echo "Creating $(ENVFILE) from example"; \
	  sudo cp uploader/.env.example $(ENVFILE); \
	  echo "Edit $(ENVFILE) to set PORT/UPLOAD_DIR/UPLOAD_TOKEN"; \
	fi

start:
	sudo systemctl start $(SERVICE)

stop:
	sudo systemctl stop $(SERVICE)

restart:
	sudo systemctl restart $(SERVICE)

status:
	sudo systemctl status $(SERVICE) --no-pager

logs:
	sudo journalctl -u $(SERVICE) -n 100 --no-pager

dev:
	# run locally from repo (not systemd)
	HOST=0.0.0.0 PORT=8765 UPLOAD_DIR=/tmp/uploads python3 -m uvicorn uploader.app.main:app --reload --port 8765

pull:
	git pull --rebase

update: deps
	# redeploy updated app files and restart
	sudo rsync -a uploader/app/ $(APP_DIR)/app/
	sudo systemctl restart $(SERVICE)

