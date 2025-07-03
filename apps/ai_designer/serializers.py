from rest_framework import serializers

class ChatInputSerializer(serializers.Serializer):
    user_input = serializers.CharField(max_length=4000)
    # thread_id is now the way to track conversations
    thread_id = serializers.UUIDField(required=False, allow_null=True)

class ChatOutputSerializer(serializers.Serializer):
    role = serializers.CharField(default="assistant")
    content = serializers.CharField()
    thread_id = serializers.UUIDField()