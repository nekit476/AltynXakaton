from django.contrib.auth.hashers import Argon2PasswordHasher


class DekanatArgon2PasswordHasher(Argon2PasswordHasher):
    """argon2id с параметрами минимума OWASP: m = 19 МиБ, t = 2, p = 1 (03_security.md §3).

    У Django по умолчанию m = 100 МиБ и p = 8: это ~100 МБ RAM на каждый вход. При 24 потоках
    gunicorn одновременные входы съели бы 2,4 ГБ — больше лимита контейнера web.
    Имя алгоритма то же ("argon2"), поэтому хеши с другими параметрами проверяются и при
    входе пересчитываются с нашими.
    """

    time_cost = 2
    memory_cost = 19 * 1024  # КиБ
    parallelism = 1
