# myapp/templatetags/dict_filters.py

from django import template

register = template.Library()

@register.filter
def get_item(lista, index):
    """
    Obtiene un elemento de una lista por su índice.
    Uso en template: {{ mi_lista|get_item:forloop.counter0 }}
    """
    try:
        return lista[index]
    except (IndexError, TypeError):
        return 0

@register.filter
def get_dict_value(dictionary, key):
    """
    Obtiene un valor de un diccionario por su clave.
    Uso en template: {{ mi_dict|get_dict_value:key }}
    """
    try:
        return dictionary.get(key, 0)
    except (AttributeError, TypeError):
        return 0