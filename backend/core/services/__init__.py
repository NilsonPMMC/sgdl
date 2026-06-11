# /var/www/sgdl/backend/core/services/__init__.py

"""
Serviços de negócio do sistema SGDL.
"""

from .carta_optimizer import CartaOptimizerService, TextOptimizationResult, PrazoInfo
from .embedding_service import EmbeddingOptimizationService

__all__ = [
    'CartaOptimizerService',
    'TextOptimizationResult', 
    'PrazoInfo',
    'EmbeddingOptimizationService',
]