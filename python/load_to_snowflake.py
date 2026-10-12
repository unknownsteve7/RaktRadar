import os
import re
import sys
import glob
import logging
# pyrefly: ignore [missing-import]
import snowflake.connector
# pyrefly: ignore [missing-import]
from cryptography.hazmat.primitives import serialization

logging.basicConfig(
    filename='eraktkosh_stock_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

STAGE = "@RAKTRADAR.RAW.RAKT_STAGE"
TABLE = "RAKTRADAR.RAW.BLOOD_STOCK"
RUN_ID_PATTERN = re.compile(r"(\d{8})_(\d{6})")

def get_connection():
    # Private key comes in as a PEM string (GitHub secret), connector wants DER bytes
    pem = os.environ["SNOWFLAKE_PRIVATE_KEY"].encode()
    passphrase = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
    key = serialization.load_pem_private_key(
        pem, password=passphrase.encode() if passphrase else None
    )
    der = key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ.get("SNOWFLAKE_USER", "RAKT_LOADER_SVC"),
        private_key=der,
        role="RAKT_LOADER",
        warehouse="RAKTRADAR_WH",
        database="RAKTRADAR",
        schema="RAW",
    )

def load_file(cur, path):
    match = RUN_ID_PATTERN.search(os.path.basename(path))
    if not match:
        raise ValueError(f"Cannot read run id from file name: {path}")
    date = match.group(1)
    # Partition the stage by date so COPY (and later cleanup) can target one day
    stage_path = f"{STAGE}/{date[:4]}/{date[4:6]}/{date[6:]}/"
    file_url = "file://" + os.path.abspath(path).replace("\\", "/")

    # File is already gzipped; AUTO_COMPRESS would wrap it again as .gz.gz
    cur.execute(f"PUT '{file_url}' {stage_path} AUTO_COMPRESS = FALSE OVERWRITE = FALSE")
    logging.info(f"PUT {path} -> {stage_path}: {cur.fetchall()}")

    # Snowflake tracks loaded files for 64 days, so re-running COPY won't duplicate rows
    cur.execute(f"""
        COPY INTO {TABLE} (raw_variant, _run_id, _source_file, _loaded_at)
        FROM (
            SELECT $1,
                   REGEXP_SUBSTR(METADATA$FILENAME, '[0-9]{{8}}_[0-9]{{6}}'),
                   METADATA$FILENAME,
                   CURRENT_TIMESTAMP()
            FROM {stage_path}
        )
        FILE_FORMAT = (FORMAT_NAME = 'RAKTRADAR.RAW.NDJSON_GZ')
    """)
    for row in cur.fetchall():
        logging.info(f"COPY result: {row}")
        print(row)

def main(pattern="blood_data_*.ndjson.gz"):
    files = sorted(glob.glob(pattern))
    if not files:
        logging.error(f"No files matching {pattern} to load.")
        sys.exit(1)

    conn = get_connection()
    try:
        cur = conn.cursor()
        for path in files:
            load_file(cur, path)
    finally:
        conn.close()
    logging.info(f"Loaded {len(files)} file(s) into {TABLE}.")

if __name__ == "__main__":
    main(*sys.argv[1:])
