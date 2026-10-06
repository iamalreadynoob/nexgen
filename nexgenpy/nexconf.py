"""# Nexgen Config.

That file contains the required configuration for the NexGen.
"""

import logging
import os

logger = logging.getLogger(__name__)


def add_config(
    mongo_conn_str: str = "mongodb://localhost:27017",
    mongo_db_name: str = "nexgen",
    mongo_coding_collection_name: str = "coding_actuators",
    mongo_decoding_collection_name: str = "decoding_actuators",
) -> None:
    """# Add Config.

    It overrides the config inside the environment. It is essential for the actuator
    decorator.

    Args:
        mongo_conn_str (str): Mongo DB connection string.
        mongo_db_name (str): The name of the database which the actuator information
            is being stored.
        mongo_coding_collection_name (str): The name of the database collection where
            the information is being stored about coding actuators.
        mongo_decoding_collection_name (str): The name of the database collection where
            the information is being stored about decoding actuators.
    """
    if isinstance(mongo_conn_str, str) is False:
        logger.error("mongo_conn_str is invalid, it has to be str")
        raise ValueError("mongo_conn_str is invalid, it has to be str")

    if isinstance(mongo_db_name, str) is False:
        logger.error("mongo_db_name is invalid, it has to be str")
        raise ValueError("mongo_db_name is invalid, it has to be str")

    if isinstance(mongo_coding_collection_name, str) is False:
        logger.error("mongo_coding_collection_name is invalid, it has to be str")
        raise ValueError("mongo_coding_collection_name is invalid, it has to be str")

    if isinstance(mongo_decoding_collection_name, str) is False:
        logger.error("mongo_decoding_collection_name is invalid, it has to be str")
        raise ValueError("mongo_decoding_collection_name is invalid, it has to be str")

    os.environ["NEXGEN_MONGO_CONNSTR"] = mongo_conn_str
    os.environ["NEXGEN_MONGO_DBNAME"] = mongo_db_name
    os.environ["NEXGEN_MONGO_C_COLNAME"] = mongo_coding_collection_name
    os.environ["NEXGEN_MONGO_D_COLNAME"] = mongo_decoding_collection_name
    logger.info("Variables have been set")
