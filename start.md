cd code_diff_project\backend; ..\venv\Scripts\python manage.py runserver 0.0.0.0:8000


cd code_diff_project\frontend; npm start

cd code_diff_project && venv\Scripts\activate && pip install hypothesis && cd backend && python -m unittest analyzer.tests.test_multi_project_tracer_properties -v
