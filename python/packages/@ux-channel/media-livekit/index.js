/**
 * @ux-channel/media-livekit
 *
 * Media plane helper (NOT a ux-bridge widget adapter).
 * Tokens/url come from ch.media.plugin(mode='sfu') / #uid-media-client.
 *
 *   import { connectFromClientJson } from '@ux-channel/media-livekit';
 *   import { Room } from 'livekit-client';
 *   const room = await connectFromClientJson(document.getElementById('uid-media-client').textContent);
 */
import { Room, RoomEvent, createLocalTracks } from "livekit-client";

export const KIND = "media-sfu";

export async function connectFromClientJson(json, opts = {}) {
  const client = typeof json === "string" ? JSON.parse(json) : json;
  if (!client?.url || !client?.token) {
    throw new Error("uid-media: missing url/token — ch.media.plugin(mode='sfu')");
  }
  const room = new Room(opts.roomOptions || {});
  await room.connect(client.url, client.token);
  if (client.canPublish !== false && opts.publish !== false) {
    try {
      const tracks = await createLocalTracks({
        audio: opts.audio !== false,
        video: opts.video !== false,
      });
      await Promise.all(tracks.map((t) => room.localParticipant.publishTrack(t)));
    } catch (e) {
      console.warn("[uid-media-livekit] publish:", e);
    }
  }
  return room;
}

export { Room, RoomEvent, createLocalTracks };
