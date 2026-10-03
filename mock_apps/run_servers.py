import asyncio
import os
import uvicorn
from mock_apps.vendor_portal import app as vendor_app
from mock_apps.finance_system import app as finance_app
from web_ui import app as web_ui_app
from mock_apps.seed import seed_database_and_pdfs

async def run():
    seed_database_and_pdfs()

    # Cloud hosts (Render, Railway) supply PORT env var for the primary web service.
    # We bind the Control Dashboard to 0.0.0.0 so external cloud routers can reach it.
    web_host = "0.0.0.0"
    web_port = int(os.getenv("PORT", 8000))

    config_web = uvicorn.Config(web_ui_app, host=web_host, port=web_port, log_level="warning")
    config_vendor = uvicorn.Config(vendor_app, host="127.0.0.1", port=8001, log_level="warning")
    config_finance = uvicorn.Config(finance_app, host="127.0.0.1", port=8002, log_level="warning")

    server_web = uvicorn.Server(config_web)
    server_vendor = uvicorn.Server(config_vendor)
    server_finance = uvicorn.Server(config_finance)

    print("================================================================")
    print(f"🚀 Control Dashboard:     http://{web_host}:{web_port}")
    print("🏢 Vendor Portal (Mock):  http://127.0.0.1:8001")
    print("💼 Finance System (Mock): http://127.0.0.1:8002")
    print("================================================================")

    await asyncio.gather(
        server_web.serve(),
        server_vendor.serve(),
        server_finance.serve()
    )

if __name__ == "__main__":
    asyncio.run(run())
