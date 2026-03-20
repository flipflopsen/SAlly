

## Hot Reload (only Dev)
Run Frontend with:
```
cd simbuilder/frontend
pnpm run dev
```

Set DEBUG flag in `.env` to True.

Run Django BE with: 
```
reloadium run manage.py runserver 127.0.0.1:8001 
```

Visit page on /editor endpoint:
`http://127.0.0.1:8001/editor/`

Hot Reload should work now for both frontend and backend.

## For prod
python manage.py collectstatic -c --noinput 