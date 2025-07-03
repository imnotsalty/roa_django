from rest_framework import serializers

class ChatInputSerializer(serializers.Serializer):
    user_input = serializers.CharField()
    history = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=[]
    )