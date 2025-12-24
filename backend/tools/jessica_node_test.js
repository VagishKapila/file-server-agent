import Vapi from "@vapi-ai/node";
import "dotenv/config";

const vapi = new Vapi({
  apiKey: process.env.VAPI_PRIVATE_KEY,
});

async function run() {
  try {
    const call = await vapi.calls.create({
      assistantId: process.env.VAPI_ASSISTANT_ID,
      phoneNumberId: process.env.VAPI_PHONE_NUMBER_ID,
      customer: {
        number: "+14084106151",
      },
      assistantOverrides: {
        firstMessage: "Hi, this is Jessica. Node SDK verification call.",
        context: {
          source: "node-sdk-test",
        },
      },
    });

    console.log("✅ Call created:", call.id);
  } catch (err) {
    console.error("❌ Node SDK call failed:", err);
  }
}

run();
