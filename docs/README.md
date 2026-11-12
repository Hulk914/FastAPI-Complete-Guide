# FastAPI Field Guide

Open [the PDF](FastAPI-Field-Guide.pdf) for the concept-first tutorial and 48 mock
interview questions with model answers, grouped into Easy, Medium, Hard, and
Architect sections.

The guide covers the HTTP/application model, validation, dependencies, synchronous
and asynchronous execution, relational modeling, transactions, CRUD, configuration,
password handling, JWT/OAuth concepts, authorization, errors, migrations, testing,
debugging, deployment, and advanced extensions. Examples labeled **REPOSITORY**
are extracted from the actual source files; features discussed as extensions are
not claimed to be implemented in the small API.

## Regenerate the PDF

From the project root, with the virtual environment active:

```text
python -m pip install -r requirements/docs.txt
python tools/build_tutorial.py
```

Edit [tutorial.md](tutorial.md) to change the prose. Code directives identify a
Python file and function/class, and the builder extracts the source and current
line numbers with Python's AST. Rebuild after code changes so those excerpts stay
current. The builder also supports tables, links, callouts, and small vector
diagrams, and embeds ReportLab's bundled fonts for consistent rendering.

The source intentionally uses a small set of Markdown conventions plus code,
diagram, and page-break directives understood by the builder. The PDF is the
finished reading format. PyMuPDF is included for rendering pages during visual
quality checks; it is not an application dependency.
