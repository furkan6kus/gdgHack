import os


def deco(fn):
    return fn


@deco
def decorated(x):
    return x


class Greeter:
    def hello(self, name):
        def inner():
            return name

        return inner()


def risky(code):
    try:
        return eval(code)
    except:
        return None
