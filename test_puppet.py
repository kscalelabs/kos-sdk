from ks_digital_twin.puppet.mujoco_puppet import MujocoPuppet
import asyncio
from loguru import logger


async def main():
    try:
        puppet = MujocoPuppet("zbot-v2")
        logger.info("MujocoPuppet initialized")

        # Get joint names
        joint_names = await puppet.get_joint_names()
        logger.info(f"Joint names: {joint_names}")

        # Get MuJoCo model and data
        model, data = await puppet.get_mj_model_and_data()
        logger.info(f"Joint positions from qpos: {data.qpos}")

        await asyncio.sleep(5)  # Keep window open

    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
