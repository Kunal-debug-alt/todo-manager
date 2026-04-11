from django import template

register = template.Library()


@register.filter
def split_tags(value):
    if not value:
        return []
    parts = [p.strip() for p in str(value).split(',')]
    return [p for p in parts if p]
