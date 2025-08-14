import { AccessToken } from "livekit-server-sdk";
import { NextRequest, NextResponse } from "next/server";

// Get LiveKit credentials from environment variables
const livekitHost = process.env.LIVEKIT_URL;
const apiKey = process.env.LIVEKIT_API_KEY;
const apiSecret = process.env.LIVEKIT_API_SECRET;

// Ensure all environment variables are set
if (!livekitHost || !apiKey || !apiSecret) {
  throw new Error("LiveKit environment variables are not set.");
}

// Next.js Route Handler for generating the token
export async function GET(req: NextRequest) {
  // Extract room and username from the request's query parameters
  const { searchParams } = new URL(req.url);
  const room = searchParams.get("room");
  const username = searchParams.get("username");

  if (!room || !username) {
    return NextResponse.json(
      { error: "Missing room or username" },
      { status: 400 }
    );
  }

  // Create an access token
  const at = new AccessToken(apiKey, apiSecret, {
    identity: username,
  });

  // Grant the participant the ability to join the room and publish/subscribe to tracks
  at.addGrant({ roomJoin: true, room: room, canPublish: true, canSubscribe: true });

  // Get the JWT token
  const token = await at.toJwt();

  return NextResponse.json({ token }, { status: 200 });
}