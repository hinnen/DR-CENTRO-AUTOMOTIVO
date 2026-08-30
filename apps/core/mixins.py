class QueryStringMixin:
    """Preserva os filtros ao trocar de página.

    Sem isso, ir para a página 2 de uma busca filtrada devolveria a lista
    inteira — e o usuário perderia o que estava procurando.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        context["querystring"] = params.urlencode()
        return context
