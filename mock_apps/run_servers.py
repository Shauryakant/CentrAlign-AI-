import asyncio
import uvicorn
from mock_apps.vendor_portal import app as vendor_app
from mock_apps.finance_system import app as finance_app
from web_ui import app as web_ui_app
from mock_apps.seed import seed_database_and_pdfs

async def run():
    seed_database_and_pdfs()

    config_web = uvicorn.Config(web_ui_app, host="127.0.0.1", port=8000, log_level="warning")
    config_vendor = uvicorn.Config(vendor_app, host="127.0.0.1", port=8001, log_level="warning")
    config_finance = uvicorn.Config(finance_app, host="127.0.0.1", port=8002, log_level="warning")

    server_web = uvicorn.Server(config_web)
    server_vendor = uvicorn.Server(config_vendor)
    server_finance = uvicorn.Server(config_finance)

    print("================================================================")
    print("🚀 Control Dashboard:     http://127.0.0.1:8000")
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
