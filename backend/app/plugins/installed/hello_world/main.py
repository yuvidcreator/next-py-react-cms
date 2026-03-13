"""Hello World Plugin — demonstrates hooks, filters, custom routes."""
import random
from backend.app.plugins.base_plugin import BasePlugin
from backend.app.core.hooks import CoreHooks, HookPriority

GREETINGS = ["Hello, World!", "Bonjour, le monde!", "Hola, Mundo!", "こんにちは世界",
             "Namaste Duniya!", "Ciao, Mondo!", "Olá, Mundo!"]

class HelloWorldPlugin(BasePlugin):
    def register_hooks(self):
        self.hooks.add_filter(CoreHooks.THE_CONTENT, self._content_filter,
                              priority=HookPriority.LATE, source=self.slug)
        self.hooks.add_action(CoreHooks.SAVE_POST, self._on_save, source=self.slug)

    def _content_filter(self, content: str) -> str:
        g = random.choice(GREETINGS)
        return f'{content}\n<p class="hello-greeting">{g}</p>'

    async def _on_save(self, **kwargs):
        entity = kwargs.get("entity")
        if entity:
            self.logger.info("Post saved: %s", getattr(entity, "title", "?"))

    def register_routes(self, router):
        @router.get("/greetings")
        async def greetings():
            return {"greetings": GREETINGS, "plugin": self.name}
        @router.get("/greetings/random")
        async def random_greeting():
            return {"greeting": random.choice(GREETINGS)}

    async def activate(self):
        await super().activate()
    async def deactivate(self):
        await super().deactivate()
