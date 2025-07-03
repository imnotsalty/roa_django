from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .logic.agent_setup import run_agent_conversation
from .serializers import ChatInputSerializer, ChatOutputSerializer
from .models import ConversationThread

class AgentChatView(APIView):
    """
    An API endpoint to interact with the AI Design Agent using conversation threads.
    """
    def post(self, request, *args, **kwargs):
        serializer = ChatInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        user_input = validated_data['user_input']
        thread_id = validated_data.get('thread_id')

        # --- Thread Management ---
        if thread_id:
            try:
                thread = ConversationThread.objects.get(id=thread_id)
                history = thread.history
                agent_context = thread.agent_context
            except ConversationThread.DoesNotExist:
                return Response({"error": "Invalid thread_id"}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Create a new thread if no ID is provided
            thread = ConversationThread.objects.create()
            history = []
            agent_context = {}

        # --- Run Agent Logic ---
        # The agent logic is now stateless and relies on passed-in history and context
        agent_response, new_agent_context = run_agent_conversation(user_input, history, agent_context)

        # --- Update and Save Thread State ---
        thread.history.append({"role": "user", "content": user_input})
        thread.history.append({"role": "assistant", "content": agent_response})
        thread.agent_context = new_agent_context
        thread.save()
        
        # --- Serialize and Return Response ---
        output_data = {
            "content": agent_response,
            "thread_id": thread.id
        }
        output_serializer = ChatOutputSerializer(data=output_data)
        output_serializer.is_valid(raise_exception=True)

        return Response(output_serializer.data, status=status.HTTP_200_OK)