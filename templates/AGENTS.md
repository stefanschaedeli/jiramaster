# Templates Directory

Jinja2 templates for JiraMaster, organized by blueprint name.

## Structure

```
templates/
  base.html           # Base layout — extends this in all pages
  {blueprint}/
    index.html        # Main page for that blueprint
```

## Conventions

### Extending base.html
Every page template must start with:
```html
{% extends "base.html" %}
{% block title %}Page Title | JiraMaster{% endblock %}
{% block content %}
  ...page content...
{% endblock %}
```

### CSRF Protection
Every `<form>` that submits via POST MUST include the CSRF token:
```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```
For AJAX requests, include `X-CSRFToken` header:
```js
headers: { 'X-CSRFToken': csrfToken }
```

### Static Assets
Reference static files via `url_for`:
```html
{{ url_for('static', filename='style.css') }}
{{ url_for('static', filename='app.js') }}
```

### URL Generation
Always use `url_for` for links and form actions:
```html
<form action="{{ url_for('tools.refresh_assignees') }}" method="POST">
```

### JavaScript
Inline scripts go in `{% block scripts %}` at the bottom of the template:
```html
{% block scripts %}
<script>
(function () {
  // scoped JS here
})();
</script>
{% endblock %}
```

## Global Context Variables

Injected by `app.py` context processor into every template:
- `cfg` — the current `JiraConfig` object (may be `None` if unconfigured)
- `app_version` — current version string from `VERSION` file

Check the route handler's `render_template()` call to see what additional variables are passed.
