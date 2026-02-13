def truncate_middle(s, n: int):
    if len(s) <= n:
        # string is already short-enough
        return s
    # half of the size, minus the 3 .'s
    n_2 = int(n / 2) - 3
    # whatever's left
    n_1 = n - n_2 - 3
    return "{}...{}".format(s[:n_1], s[-n_2:])
