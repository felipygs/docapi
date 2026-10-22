class Pagina:
    def __init__(self, sessao):
        self.sessao = sessao


class Sessao:
    def __init__(self):
        self.cookies = {}
        self.storage = {}
        self.fechada = False

    async def new_page(self):
        return Pagina(self)

    async def close(self):
        self.fechada = True


class PlaywrightLocal:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False
