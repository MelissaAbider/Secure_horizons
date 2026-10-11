.PHONY: frontend frontend-build test-t6
frontend:        ; cd frontend && npm run dev
frontend-build:  ; cd frontend && npm ci && npm run build
test-t6:         ; cd frontend && npm run typecheck && npm run build && npm run test
