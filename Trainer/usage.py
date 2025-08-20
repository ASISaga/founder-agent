# run_training.py
from founderops_trainer import Stage1GoldenTrainer, Stage2ExpansionTrainer

if __name__ == "__main__":
    # ===== Stage 1 =====
    stage1 = Stage1GoldenTrainer()
    stage1.train()

    # ===== Stage 2 =====
    stage2 = Stage2ExpansionTrainer()
    stage2.train()