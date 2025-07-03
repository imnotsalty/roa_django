# Create your models here.
import uuid
from django.db import models

class ConversationThread(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Stores the list of {'role': '...', 'content': '...'} messages
    history = models.JSONField(default=list)
    # Stores the agent's context for multi-step tool calls
    agent_context = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.id)
