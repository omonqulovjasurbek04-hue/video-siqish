from handlers.start import router as start_router
from handlers.compress import router as compress_router
from handlers.trim import router as trim_router
from handlers.merge import router as merge_router
from handlers.watermark import router as watermark_router
from handlers.gif import router as gif_router
from handlers.tools import router as tools_router
from handlers.fallback import router as fallback_router

# Tartib muhim: fallback eng oxirida bo'lishi kerak
all_routers = [
    start_router,
    compress_router,
    trim_router,
    merge_router,
    watermark_router,
    gif_router,
    tools_router,
    fallback_router,   # Always last
]
