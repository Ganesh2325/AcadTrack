from django import forms


class BootstrapFormMixin:
    """Apply Bootstrap 5 classes without replacing server-side validation."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def apply_bootstrap(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                css = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css = "form-select"
            else:
                css = "form-control"
            existing = widget.attrs.get("class", "").split()
            if css not in existing:
                existing.append(css)
            widget.attrs["class"] = " ".join(existing).strip()
