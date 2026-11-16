import importlib, sys
modules = ['Backend.services.application_service','Backend.routes.applications','Backend.models.application']
for m in modules:
    try:
        importlib.import_module(m)
        print(f"{m} ok")
    except Exception as e:
        print(f"Error importing {m}: {e}", file=sys.stderr)
        sys.exit(1)
print('All imports succeeded')
