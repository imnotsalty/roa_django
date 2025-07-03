from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .logic.agent_setup import run_agent_conversation
from .serializers import ChatInputSerializer

class AgentChatView(APIView):
    """
    An API endpoint to interact with the AI Design Agent.
    """
    def post(self, request, *args, **kwargs):
        serializer = ChatInputSerializer(data=request.data)
        if serializer.is_valid():
            user_input = serializer.validated_data['user_input']
            history = serializer.validated_data['history']
            
            # Call the agent logic
            agent_response = run_agent_conversation(user_input, history)
            
            # Construct the response payload
            response_data = {
                "role": "assistant",
                "content": agent_response
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)