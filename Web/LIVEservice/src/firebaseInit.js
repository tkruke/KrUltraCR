
// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getDatabase } from "firebase/database";
import { getAuth } from "firebase/auth";

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  apiKey: "AIzaSyApppISgdtYgJbqg9iEhFzT8X1TIh2OHFo",
  authDomain: "krultracr.firebaseapp.com",
  databaseURL: "https://krultracr-default-rtdb.europe-west1.firebasedatabase.app",
  projectId: "krultracr",
  storageBucket: "krultracr.appspot.com",
  messagingSenderId: "505845763821",
  appId: "1:505845763821:web:d1cbb080da58d7f5bcc6e4",
  measurementId: "G-F4H6VWBPLK"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const database = getDatabase(app);

export const auth = getAuth();
export const db = database; 


