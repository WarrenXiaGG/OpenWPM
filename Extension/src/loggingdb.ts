import * as socket from "./socket";

let crawlID = null;
let visitID = null;
let debugging = false;
let storageController = null;
let logAggregator = null;
let listeningSocket = null;

const listeningSocketCallback = async (data) => {
  // This works even if data is an int
  const action = data.action;
  let newVisitID = data.visit_id;
  switch (action) {
    case "Initialize":
      if (visitID) {
        logWarn("Set visit_id while another visit_id was set");
      }
      visitID = newVisitID;
      data.browser_id = crawlID;
      storageController.send(JSON.stringify(["meta_information", data]));
      break;
    case "Finalize":
      if (!visitID) {
        logWarn("Received Finalize while no visit_id was set");
      }
      if (newVisitID !== visitID) {
        logError(
          "Received Finalize but visit_id didn't match. " +
            `Current visit_id ${newVisitID}, received visit_id ${visitID}.`,
        );
      }
      data.browser_id = crawlID;
      data.success = true;
      storageController.send(JSON.stringify(["meta_information", data]));
      visitID = null;
      break;
    default:
      // Just making sure that it's a valid number before logging
      newVisitID = parseInt(data, 10);
      logDebug("Setting visit_id the legacy way");
      visitID = newVisitID;
  }
};
export const open = async function (
  storageControllerAddress,
  logAddress,
  curr_crawlID,
) {
  if (
    storageControllerAddress == null &&
    logAddress == null &&
    curr_crawlID === 0
  ) {
    console.log("Debugging, everything will output to console");
    debugging = true;
    return;
  }
  crawlID = curr_crawlID;

  console.log("Opening socket connections...");

  // Connect to MPLogger for extension info/debug/error logging
  if (logAddress != null) {
    logAggregator = new socket.SendingSocket();
    const rv = await logAggregator.connect(logAddress[0], logAddress[1]);
    console.log("logSocket started?", rv);
  }

  // Connect to databases for saving data
  if (storageControllerAddress != null) {
    storageController = new socket.SendingSocket();
    const rv = await storageController.connect(
      storageControllerAddress[0],
      storageControllerAddress[1],
    );
    console.log("StorageController started?", rv);
  }
  storageController.send(JSON.stringify(`Browser-${crawlID}`));
  // Listen for incoming urls as visit ids
  listeningSocket = new socket.ListeningSocket(listeningSocketCallback);
  console.log("Starting socket listening for incoming connections.");
  await listeningSocket.startListening().then(() => {
    (browser as any).profileDirIO.writeFile(
      "extension_port.txt",
      `${listeningSocket.port}`,
    );
  });
};

export const close = function () {
  if (storageController != null) {
    storageController.close();
  }
  if (logAggregator != null) {
    logAggregator.close();
  }
};

const makeLogJSON = function (lvl, msg) {
  const log_json = {
    name: "Extension-Logger",
    level: lvl,
    pathname: "FirefoxExtension",
    lineno: 1,
    msg: escapeString(msg),
    args: null,
    exc_info: null,
    func: null,
  };
  return log_json;
};

export const logInfo = function (msg) {
  // Always log to browser console
  console.log(msg);

  if (debugging) {
    return;
  }

  // Log level INFO == 20 (https://docs.python.org/2/library/logging.html#logging-levels)
  const log_json = makeLogJSON(20, msg);
  logAggregator.send(JSON.stringify(["EXT", JSON.stringify(log_json)]));
};

export const logDebug = function (msg) {
  // Always log to browser console
  console.log(msg);

  if (debugging) {
    return;
  }

  // Log level DEBUG == 10 (https://docs.python.org/2/library/logging.html#logging-levels)
  const log_json = makeLogJSON(10, msg);
  logAggregator.send(JSON.stringify(["EXT", JSON.stringify(log_json)]));
};

export const logWarn = function (msg) {
  // Always log to browser console
  console.warn(msg);

  if (debugging) {
    return;
  }

  // Log level WARN == 30 (https://docs.python.org/2/library/logging.html#logging-levels)
  const log_json = makeLogJSON(30, msg);
  logAggregator.send(JSON.stringify(["EXT", JSON.stringify(log_json)]));
};

export const logError = function (msg) {
  // Always log to browser console
  console.error(msg);

  if (debugging) {
    return;
  }

  // Log level INFO == 40 (https://docs.python.org/2/library/logging.html#logging-levels)
  const log_json = makeLogJSON(40, msg);
  logAggregator.send(JSON.stringify(["EXT", JSON.stringify(log_json)]));
};

export const logCritical = function (msg) {
  // Always log to browser console
  console.error(msg);

  if (debugging) {
    return;
  }

  // Log level CRITICAL == 50 (https://docs.python.org/2/library/logging.html#logging-levels)
  const log_json = makeLogJSON(50, msg);
  logAggregator.send(JSON.stringify(["EXT", JSON.stringify(log_json)]));
};

export const dataReceiver = {
  saveRecord(a, b) {
    console.log(a, b);
  },
};

export const saveRecord = function (instrument, record) {
  record.visit_id = visitID;

  if (!visitID && !debugging) {
    // Navigations to about:blank can be triggered by OpenWPM. We drop those.
    if (instrument === "navigations" && record.url === "about:blank") {
      logDebug(
        "Extension-" +
          crawlID +
          " : Dropping navigation to about:blank in intermediate period",
      );
      return;
    }
    logWarn(
      `Extension-${crawlID} : visitID is null while attempting to insert into table ${instrument}\n` +
        JSON.stringify(record),
    );
    record.visit_id = -1;
  }

  // send to console if debugging
  if (debugging) {
    console.log("EXTENSION", instrument, record);
    return;
  }
  storageController.send(JSON.stringify([instrument, record]));
};

// Stub for now
export const saveContent = async function (content, contentHash) {
  // Send page content to the data aggregator
  // deduplicated by contentHash in a levelDB database
  if (debugging) {
    console.log("LDB contentHash:", contentHash, "with length", content.length);
    return;
  }
  // Since the content might not be a valid utf8 string and it needs to be
  // json encoded later, it is encoded using base64 first.
  const b64 = Uint8ToBase64(content);
  storageController.send(JSON.stringify(["page_content", [b64, contentHash]]));
};

function encode_utf8(s) {
  return unescape(encodeURIComponent(s));
}

// Base64 encoding, found on:
// https://stackoverflow.com/questions/12710001/how-to-convert-uint8-array-to-base64-encoded-string/25644409#25644409
function Uint8ToBase64(u8Arr) {
  const CHUNK_SIZE = 0x8000; // arbitrary number
  let index = 0;
  const length = u8Arr.length;
  let result = "";
  let slice;
  while (index < length) {
    slice = u8Arr.subarray(index, Math.min(index + CHUNK_SIZE, length));
    result += String.fromCharCode.apply(null, slice);
    index += CHUNK_SIZE;
  }
  return btoa(result);
}

export const escapeString = function (string) {
  // Convert to string if necessary
  if (typeof string !== "string") string = "" + string;

  return encode_utf8(string);
};

export const boolToInt = function (bool) {
  return bool ? 1 : 0;
};
