"""Права доступа: разрешения (Perm), роли как наборы разрешений, декоратор require_perm.

Как пользоваться во view (web/):

    from core.access import Perm, require_perm

    @require_perm(Perm.CREATE_REQUESTS)
    def request_list(request): ...

Публичный адрес помечается `@login_not_required` и вносится в core/access/public.py.
"""

from core.access.decorators import require_perm
from core.access.perms import Perm

__all__ = ("Perm", "require_perm")
