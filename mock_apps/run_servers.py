import asyncio
import uvicorn
from mock_apps.vendor_portal import app as vendor_app
from mock_apps.finance_system import app as finance_app
from mock_apps.seed import seed_database_and_pdfs

async def run():
    seed_database_and_pdfs()

    config_vendor = uvicorn.Config(vendor_app, host="127.0.0.1", port=8001, log_level="warning")
    config_finance = uvicorn.Config(finance_app, host="127.0.0.1", port=8002, log_level="warning")

    server_vendor = uvicorn.Server(config_vendor)
    server_finance = uvicorn.Server(config_finance)

    print("Starting Vendor Portal on http://127.0.0.1:8001")
    print("Starting Internal Finance System on http://127.0.0.1:8002")

    await asyncio.gather(
        server_vendor.serve(),
        server_finance.serve()
    )

if __name__ == "__main__":
    asyncio.run(run())
