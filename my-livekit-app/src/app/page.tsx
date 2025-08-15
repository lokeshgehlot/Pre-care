"use client";

import { useState, useEffect } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  AudioConference,
} from "@livekit/components-react";
import "@livekit/components-styles";

// This is the component that handles the LiveKit connection
function MyLiveKitApp() {
  const [userToken, setUserToken] = useState<string | null>(null);
  const [agentToken, setAgentToken] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [participantName, setParticipantName] = useState<string | null>(null);

  // The room name will be hardcoded for this example
  const roomName = "Medical Assistance";

  // Use useEffect to generate the participant name only on the client side
  useEffect(() => {
    // This code runs only in the browser, preventing hydration mismatch
    setParticipantName("Web-User-" + Math.floor(Math.random() * 1000));
  }, []);

  // Function to fetch the tokens from our local Next.js API route
  const getTokens = async () => {
    setIsConnecting(true);
    setError(null);
    try {
      if (!participantName) {
        throw new Error("Participant name is not set.");
      }
      
      // Fetch the token for the user
      const userResponse = await fetch(`/api/token?room=${roomName}&username=${participantName}`);
      if (!userResponse.ok) {
        throw new Error("Failed to fetch user token from server.");
      }
      const userData = await userResponse.json();
      setUserToken(userData.token);

      // Fetch the token for the agent, which triggers the agent job
      const agentResponse = await fetch(`/api/token?room=${roomName}&username=HeyDocAI&isAgent=true`);
      if (!agentResponse.ok) {
        throw new Error("Failed to fetch agent token from server.");
      }
      const agentData = await agentResponse.json();
      setAgentToken(agentData.token);

    } catch (e: any) {
      console.error(e);
      setError("An error occurred while fetching the tokens.");
    } finally {
      setIsConnecting(false);
    }
  };

  if (error) {
    return (
      <div className="container">
        <div className="error-box">
          <h1 className="title">Connection Error</h1>
          <p>{error}</p>
          <button onClick={getTokens} className="button primary-button">
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // Show a loading state while the participant name is being generated
  if (!participantName) {
    return (
      <div className="container">
        <div className="card">
          <p className="card-text">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <header className="header">
        <h1 className="title">LiveKit Voice Agent</h1>
        <p className="subtitle">
          Click "Connect" to join the room and talk to your voice agent.
        </p>
      </header>

      <main className="main-content">
        {!userToken ? (
          <div className="card">
            <h2>Ready to Connect</h2>
            <p className="card-text">
              This will connect you and the voice agent to the room.
            </p>
            <button
              onClick={getTokens}
              disabled={isConnecting}
              className="button connect-button"
            >
              {isConnecting ? "Connecting..." : "Connect to Room"}
            </button>
          </div>
        ) : (
          <div className="card">
            <LiveKitRoom
              video={false}
              audio={true}
              token={userToken}
              serverUrl={process.env.NEXT_PUBLIC_LIVEKIT_URL}
              connect={true}
              onDisconnected={() => { setUserToken(null); setAgentToken(null); }}
            >
              <AudioConference />
              <RoomAudioRenderer />
            </LiveKitRoom>
          </div>
        )}
      </main>

      <footer className="footer">
        <p>Your participant name: <span className="mono">{participantName}</span></p>
        <p>Room name: <span className="mono">{roomName}</span></p>
      </footer>
    </div>
  );
}

export default function App() {
  return <MyLiveKitApp />;
}
