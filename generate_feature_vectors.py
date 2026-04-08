#!/usr/bin/env python
"""
生成题目特征向量脚本
为ATMR题库中的每道题生成语义特征向量，用于智能选题算法。
"""

import json
import sys
import numpy as np
from pathlib import Path

# 检查并安装依赖
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.decomposition import PCA
except ImportError as e:
    print(f"[ERROR] 缺少依赖: {e}")
    print("请安装所需依赖: pip install sentence-transformers scikit-learn numpy torch")
    sys.exit(1)

from app.models.question import SessionLocal, Question


class FeatureVectorGenerator:
    """题目特征向量生成器"""

    def __init__(self, model_name='paraphrase-multilingual-MiniLM-L12-v2', target_dim=64):
        """
        初始化特征向量生成器

        Args:
            model_name: sentence-transformers模型名称
            target_dim: 目标维度（如果大于0，则使用PCA降维）
        """
        print(f"[LOAD] 加载模型: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.original_dim = self.model.get_sentence_embedding_dimension()
        self.target_dim = target_dim
        self.pca = None if target_dim <= 0 else PCA(n_components=target_dim)

        print(f"[OK] 模型加载完成，原始维度: {self.original_dim}")
        if target_dim > 0:
            print(f"[DIM] 目标维度: {target_dim} (PCA降维)")

    def generate_text_for_embedding(self, question_data):
        """生成用于嵌入的文本"""
        text_parts = []

        # 题干
        exam = question_data.get('exam', '')
        if exam:
            text_parts.append(f"题目: {exam}")

        # 选项
        options = question_data.get('options', [])
        if options:
            options_text = " ".join([f"选项{i+1}: {opt}" for i, opt in enumerate(options)])
            text_parts.append(f"选择: {options_text}")

        # 官方解析（如果有）
        description = question_data.get('description', '')
        if description:
            text_parts.append(f"解析: {description}")

        # 特质标签（如果有）
        trait_label = question_data.get('title', '')
        if trait_label:
            text_parts.append(f"特质: {trait_label}")

        return " ".join(text_parts)

    def generate_feature_vector(self, question_data):
        """为单个题目生成特征向量"""
        text = self.generate_text_for_embedding(question_data)

        # 生成原始嵌入向量
        embedding = self.model.encode(text)

        return embedding

    def fit_pca(self, all_vectors):
        """使用所有向量训练PCA降维器"""
        if self.pca is not None:
            print("[TRAIN] 训练PCA降维模型...")
            self.pca.fit(all_vectors)
            explained_variance = sum(self.pca.explained_variance_ratio_)
            print(f"[OK] PCA训练完成，保留方差: {explained_variance:.2%}")

    def reduce_dimension(self, vector):
        """降维（如果启用）"""
        if self.pca is not None:
            # 重塑为2D数组
            vector_2d = vector.reshape(1, -1)
            reduced = self.pca.transform(vector_2d)
            return reduced.flatten()
        return vector

    def update_database_features(self, db, question, feature_vector,
                                  difficulty=None, discrimination=None):
        """更新数据库中的特征向量和题目参数"""
        vector_list = feature_vector.tolist() if hasattr(feature_vector, 'tolist') else feature_vector
        dim = len(vector_list)

        question.feature_vector = vector_list
        question.feature_dim = dim

        if difficulty is not None:
            question.difficulty = difficulty
        if discrimination is not None:
            question.discrimination = discrimination

        print(f"  [UPDATE] 更新题目 {question.exam_no}: 维度={dim}, "
              f"难度={question.difficulty:.3f}, 区分度={question.discrimination:.3f}")

    def compute_semantic_item_params(self, questions_with_vectors):
        """
        基于语义特征向量计算差异化的题目难度和区分度。

        难度由三个因素决定：
        1. 语义离群度：题目向量离同维度中心越远 → 越不典型 → 越难理解
        2. 反向计分：反向题需要逆向思维 → 加难度
        3. 语义模糊度：题目与多个维度都相似 → 语义边界模糊 → 更难

        区分度由两个因素决定：
        1. 维度内独特性：题目在维度内越独特 → 测到的东西越不可替代 → 区分度高
        2. 维度间分离度：题目与本维度的关联远强于其他维度 → 测量纯净 → 区分度高
        """
        # 按维度分组
        dim_groups = {}  # dimension_id -> [(question, vector), ...]
        for question, vector in questions_with_vectors:
            dim_id = question.dimension_id or 'unknown'
            if dim_id not in dim_groups:
                dim_groups[dim_id] = []
            dim_groups[dim_id].append((question, vector))

        # 计算每个维度的中心向量
        dim_centroids = {}
        for dim_id, items in dim_groups.items():
            vectors = np.array([v for _, v in items])
            dim_centroids[dim_id] = np.mean(vectors, axis=0)

        # 全局中心
        all_vectors = np.array([v for _, v in questions_with_vectors])
        global_centroid = np.mean(all_vectors, axis=0)

        print(f"[PARAM] 维度数: {len(dim_groups)}, 各维度题数: "
              f"{{{', '.join(f'{k}: {len(v)}' for k, v in dim_groups.items())}}}")

        # 为每道题计算参数
        results = {}  # question.id -> (difficulty, discrimination)

        for question, vector in questions_with_vectors:
            dim_id = question.dimension_id or 'unknown'
            own_centroid = dim_centroids[dim_id]
            own_group_vectors = [v for q, v in dim_groups[dim_id] if q.id != question.id]

            # ========== 难度计算 ==========

            # 因素1: 语义离群度 (0~1)
            # 到本维度中心的距离，相对于该维度的平均距离
            dist_to_own = np.linalg.norm(vector - own_centroid)
            if own_group_vectors:
                all_dists = [np.linalg.norm(v - own_centroid) for v in own_group_vectors]
                mean_dist = np.mean(all_dists)
                std_dist = np.std(all_dists) + 1e-10
                # z-score 标准化后用 sigmoid 映射到 0~1
                z_outlier = (dist_to_own - mean_dist) / std_dist
                outlier_score = 1.0 / (1.0 + np.exp(-z_outlier))
            else:
                outlier_score = 0.5

            # 因素2: 反向计分加成
            reverse_bonus = 0.12 if question.is_reverse else 0.0

            # 因素3: 语义模糊度 (0~1)
            # 与其他维度中心的相似度，越高越模糊
            other_sims = []
            for other_dim, centroid in dim_centroids.items():
                if other_dim != dim_id:
                    cos_sim = self._cosine_sim(vector, centroid)
                    other_sims.append(cos_sim)

            if other_sims:
                # 取与其他维度的最大相似度作为模糊度
                ambiguity = float(max(other_sims))
                # 归一化到 0~1（相似度范围通常在 0.5~1.0 之间）
                ambiguity = np.clip((ambiguity - 0.3) / 0.5, 0.0, 1.0)
            else:
                ambiguity = 0.5

            # 综合难度
            difficulty = (
                0.50 * outlier_score +
                0.30 * ambiguity +
                0.20 * 0.5  # 基线
                + reverse_bonus
            )
            difficulty = float(np.clip(difficulty, 0.10, 0.95))

            # ========== 区分度计算 ==========

            # 因素1: 维度内独特性 (0~1)
            # 与同维度其他题目的平均余弦相似度越低 → 越独特
            if own_group_vectors:
                intra_sims = [self._cosine_sim(vector, v) for v in own_group_vectors]
                avg_intra_sim = float(np.mean(intra_sims))
                uniqueness = 1.0 - np.clip((avg_intra_sim - 0.3) / 0.5, 0.0, 1.0)
            else:
                uniqueness = 0.5

            # 因素2: 维度间分离度 (0~1)
            # 与本维度中心的相似度 vs 与其他维度中心的最大相似度
            sim_to_own = self._cosine_sim(vector, own_centroid)
            if other_sims:
                max_other_sim = max(other_sims)
                # 差距越大 → 分离度越高
                separation = np.clip(sim_to_own - max_other_sim, 0.0, 0.5) * 2.0
            else:
                separation = 0.5

            # 综合区分度
            discrimination = (
                0.55 * uniqueness +
                0.45 * separation
            )
            discrimination = float(np.clip(discrimination, 0.10, 0.95))

            results[question.id] = (difficulty, discrimination)

        return results

    def _cosine_sim(self, a, b):
        """计算余弦相似度"""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    def process_all_questions(self, db, target_dim=64):
        """处理所有题目"""
        print("[SEARCH] 从数据库加载所有题目...")
        all_questions = db.query(Question).all()

        if not all_questions:
            print("[ERROR] 数据库中没有题目，请先运行 import_data.py")
            return 0

        print(f"[STAT] 找到 {len(all_questions)} 道题目")

        # 第一步：生成所有原始向量
        print("[GEN] 生成特征向量...")
        all_vectors = []
        questions_with_vectors = []

        for i, question in enumerate(all_questions):
            print(f"  [{i+1}/{len(all_questions)}] 处理: {question.exam_no}")

            # 构建题目数据
            question_data = {
                'exam': question.content,
                'options': question.options,
                'description': question.ai_analysis_prompt,
                'title': question.trait_label,
                'scores': question.scores
            }

            # 生成向量
            vector = self.generate_feature_vector(question_data)
            all_vectors.append(vector)
            questions_with_vectors.append((question, vector))

        # 转换为numpy数组
        all_vectors = np.array(all_vectors)

        # 第二步：如果需要降维，训练PCA
        if self.target_dim > 0 and self.target_dim < self.original_dim:
            print(f"[REDUCE] 应用PCA降维: {self.original_dim} -> {self.target_dim}")
            self.pca = PCA(n_components=self.target_dim)
            self.pca.fit(all_vectors)
            explained_variance = sum(self.pca.explained_variance_ratio_)
            print(f"[OK] PCA降维完成，保留方差: {explained_variance:.2%}")

        # 第三步：降维（如果需要）
        final_questions_vectors = []
        for question, original_vector in questions_with_vectors:
            if self.pca is not None:
                vector_2d = original_vector.reshape(1, -1)
                reduced_vector = self.pca.transform(vector_2d).flatten()
                final_questions_vectors.append((question, reduced_vector))
            else:
                final_questions_vectors.append((question, original_vector))

        # 第四步：基于语义特征计算差异化的难度和区分度
        print("[PARAM] 基于语义特征计算题目参数...")
        item_params = self.compute_semantic_item_params(final_questions_vectors)

        # 打印参数分布统计
        difficulties = [v[0] for v in item_params.values()]
        discriminations = [v[1] for v in item_params.values()]
        print(f"[STAT] 难度分布: min={min(difficulties):.3f}, max={max(difficulties):.3f}, "
              f"mean={np.mean(difficulties):.3f}, std={np.std(difficulties):.3f}")
        print(f"[STAT] 区分度分布: min={min(discriminations):.3f}, max={max(discriminations):.3f}, "
              f"mean={np.mean(discriminations):.3f}, std={np.std(discriminations):.3f}")

        # 第五步：更新数据库
        print("[SAVE] 更新数据库...")
        updated_count = 0

        for question, vector in final_questions_vectors:
            difficulty, discrimination = item_params.get(question.id, (0.5, 0.5))
            self.update_database_features(db, question, vector,
                                          difficulty=difficulty,
                                          discrimination=discrimination)
            updated_count += 1

        db.commit()
        return updated_count


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='生成题目特征向量')
    parser.add_argument('--model', type=str, default='paraphrase-multilingual-MiniLM-L12-v2',
                       help='sentence-transformers模型名称')
    parser.add_argument('--dim', type=int, default=64,
                       help='目标维度（<=0表示不降维，>0表示使用PCA降维到该维度）')
    parser.add_argument('--recreate-db', action='store_true',
                       help='重新创建数据库（删除现有特征向量）')

    args = parser.parse_args()

    # 连接数据库
    print("[CONNECT] 连接数据库...")
    db = SessionLocal()

    try:
        # 如果需要，清空现有特征向量
        if args.recreate_db:
            print("[CLEAR]  清空现有特征向量...")
            for question in db.query(Question).all():
                question.feature_vector = None
                question.feature_dim = None
            db.commit()
            print("[OK] 特征向量已清空")

        # 创建生成器
        generator = FeatureVectorGenerator(model_name=args.model, target_dim=args.dim)

        # 处理所有题目
        updated = generator.process_all_questions(db, target_dim=args.dim)

        print(f"\n[DONE] 处理完成！成功更新 {updated} 道题目的特征向量")

        # 统计信息
        questions_with_features = db.query(Question).filter(Question.feature_vector.isnot(None)).count()
        print(f"[STAT] 数据库中有 {questions_with_features} 道题具有特征向量")

        if questions_with_features > 0:
            sample = db.query(Question).filter(Question.feature_vector.isnot(None)).first()
            if sample and sample.feature_vector:
                print(f"[DIM] 特征向量维度: {sample.feature_dim}")
                print(f"[PARAM] 样本难度: {sample.difficulty:.2f}, 区分度: {sample.discrimination:.2f}")

    except Exception as e:
        print(f"[ERROR] 处理过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 1
    finally:
        db.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())