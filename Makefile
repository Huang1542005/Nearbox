.PHONY: help up down restart logs reset test seed shell schema createadmin

help:
	@echo "Lệnh hữu ích cho NearBox Backend:"
	@echo "  make up          - Khởi động tất cả dịch vụ (db, web, scheduler) bằng Docker Compose"
	@echo "  make down        - Dừng toàn bộ các dịch vụ"
	@echo "  make restart     - Khởi động lại dịch vụ web"
	@echo "  make logs        - Xem log theo thời gian thực"
	@echo "  make test        - Chạy bộ kiểm thử pytest trong container web"
	@echo "  make seed        - Chạy khởi tạo dữ liệu mẫu (seed_demo)"
	@echo "  make reset       - Xóa và tái khởi động database, migrate và nạp seed data"
	@echo "  make shell       - Mở Django shell tương tác"
	@echo "  make schema      - Xuất OpenAPI schema ra docs/openapi.yaml"
	@echo "  make createadmin - Tạo tài khoản superuser mẫu"

up:
	docker compose up -d --build

down:
	docker compose down

restart:
	docker compose restart web

logs:
	docker compose logs -f

test:
	docker compose exec web pytest -v

seed:
	docker compose exec web python manage.py seed_demo

reset:
	docker compose down -v
	docker compose up -d --build
	docker compose exec web python manage.py migrate
	docker compose exec web python manage.py seed_demo

shell:
	docker compose exec web python manage.py shell

schema:
	docker compose exec web python manage.py spectacular --file docs/openapi.yaml

createadmin:
	docker compose exec web python -c "from apps.accounts.models import User; u, _ = User.objects.get_or_create(phone='0900000000', defaults={'full_name':'Admin Concierge', 'building':'S1', 'unit_number':'1001', 'is_staff':True, 'is_superuser':True, 'is_resident_verified':True}); u.set_password('admin123'); u.save(); print('Admin ready: phone 0900000000 / pass admin123')"
