from flask import Flask, session,render_template,request
import pymysql 
import cv2
from tensorflow.keras.models import load_model
import numpy as np
from collections import deque
import zipfile
import pyzipper
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import os

app = Flask(__name__)

UPLOAD_AUDIO_FOLDER = 'static/audiofiles/'
app.config['UPLOAD_AUDIO_FOLDER'] = UPLOAD_AUDIO_FOLDER

def dbConnection():
    try:
        connection = pymysql.connect(host="localhost", user="root", password="root", database="suspiciousactdetection")
        return connection
    except:
        print("Something went wrong in database Connection")

def dbClose():
    try:
        dbConnection().close()
    except:
        print("Something went wrong in Close DB Connection")

app.secret_key = 'any random string'

con = dbConnection()
cursor = con.cursor()

loaded_model = load_model("MoBiLSTM_Detection_model.h5")
IMAGE_HEIGHT , IMAGE_WIDTH = 64, 64
SEQUENCE_LENGTH = 16
CLASSES_LIST = ["Normal","Suspicious"]
    
@app.route("/",methods=['POST','GET'])
def index():    
    return render_template('index.html')

@app.route("/register",methods=['POST','GET'])
def register():    
    return render_template('register.html')

@app.route("/login",methods=['POST','GET'])
def login():    
    return render_template('login.html')

@app.route("/home",methods=['POST','GET'])
def home():    
    return render_template('home.html')

@app.route('/logout')
def logout():
    session.pop('name',None)
    return render_template('login.html') 
    
def zip_with_password(input_file, output_zip, password):
    with pyzipper.AESZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(password)
        zf.write(input_file)

def sendvideofilemailtouser(usermail,output_zip_file):
    sender_email = "seemareddy004@gmail.com"
    receiver_email = usermail
    password = "namquyrjzktyuqps"
    
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = "Password-protected Video Attachment"
    
    body = "Suspicious activity detected. Dear user, password to open this file is your account password !"
    message.attach(MIMEText(body, "plain"))
    
    filename = output_zip_file
    attachment_path = output_zip_file
    # Create a MIMEBase object
    with open(attachment_path, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
    
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f"attachment; filename= {filename}",
    )
    
    message.attach(part)
    text = message.as_string()
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, text)
    
    print("Email sent successfully!")

def count_consecutive(data, target, n):
    count = 0
    for item in data:
        if item == target:
            count += 1
            if count >= n:
                return True
        else:
            count = 0
    return False

# Define a global variable or a flag to control the loop
stop_video_processing = False

# Function to stop the video processing loop
def stop_video_processing_loop():
    global stop_video_processing
    stop_video_processing = True
    
@app.route('/startAnamolyDetection',methods=['POST','GET'])
def startAnamolyDetection():    
    if request.method == "POST":
        details = request.form
        name = details['name']
        print(name)
        
        global stop_video_processing
        stop_video_processing = False
        
        returntext = 'Normal'
        # video_reader = cv2.VideoCapture("test_videos/s4.mp4")
        video_reader = cv2.VideoCapture(0)

        # Define the dimensions of the video
        width = int(video_reader.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(video_reader.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = 30
        
        # Create a VideoWriter object
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter('output_video.avi', fourcc, fps, (width, height)) 
        
        frames_queue = deque(maxlen = SEQUENCE_LENGTH)
        predicted_class_name = ''
        deciderlist=[]    
        
        while video_reader.isOpened() and not stop_video_processing:
        # while (True):
            ok, frame = video_reader.read()             
            if not ok:
                break
        
            resized_frame = cv2.resize(frame, (IMAGE_HEIGHT, IMAGE_WIDTH))
            normalized_frame = resized_frame / 255
            frames_queue.append(normalized_frame)
            if len(frames_queue) == SEQUENCE_LENGTH:                        
                predicted_labels_probabilities = loaded_model.predict(np.expand_dims(frames_queue, axis = 0))[0]
                predicted_label = np.argmax(predicted_labels_probabilities)
                predicted_class_name = CLASSES_LIST[predicted_label]
        
                deciderlist.append(predicted_class_name)
            if predicted_class_name == "Suspicious":
                cv2.putText(frame, predicted_class_name, (5, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
            else:
                cv2.putText(frame, predicted_class_name, (5, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
                
            cv2.imshow('frame', frame) 
            out.write(frame)       
            
            if count_consecutive(deciderlist, 'Suspicious', 50):
                returntext = 'Suspicious'
                break            
        
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
        video_reader.release()
        out.release()
        cv2.destroyAllWindows()
        
        if returntext == 'Suspicious':   
            print()
            print(session.get("userpass"))
            print(session.get("useremail"))
            print()
            input_video_file = 'output_video.avi'
            output_zip_file = 'video.zip'   
            passwordforlock = session.get("userpass")
            
            zip_with_password(input_video_file, output_zip_file, passwordforlock.encode())
            
            useremail = session.get("useremail")
            sendvideofilemailtouser(useremail,output_zip_file)
            
            os.remove('output_video.avi')
            os.remove('video.zip')
        return returntext
    
def predict_video(video_file_path, SEQUENCE_LENGTH):
 
    video_reader = cv2.VideoCapture(video_file_path)
 
    # Declare a list to store video frames we will extract.
    frames_list = []
    
    # Store the predicted class in the video.
    predicted_class_name = ''
 
    # Get the number of frames in the video.
    video_frames_count = int(video_reader.get(cv2.CAP_PROP_FRAME_COUNT))
 
    # Calculate the interval after which frames will be added to the list.
    skip_frames_window = max(int(video_frames_count/SEQUENCE_LENGTH),1)
 
    # Iterating the number of times equal to the fixed length of sequence.
    for frame_counter in range(SEQUENCE_LENGTH):
 
        # Set the current frame position of the video.
        video_reader.set(cv2.CAP_PROP_POS_FRAMES, frame_counter * skip_frames_window)
 
        success, frame = video_reader.read() 
 
        if not success:
            break
 
        # Resize the Frame to fixed Dimensions.
        resized_frame = cv2.resize(frame, (IMAGE_HEIGHT, IMAGE_WIDTH))
        
        # Normalize the resized frame.
        normalized_frame = resized_frame / 255
        
        # Appending the pre-processed frame into the frames list
        frames_list.append(normalized_frame)
 
    # Passing the  pre-processed frames to the model and get the predicted probabilities.
    predicted_labels_probabilities = loaded_model.predict(np.expand_dims(frames_list, axis = 0))[0]
 
    # Get the index of class with highest probability.
    predicted_label = np.argmax(predicted_labels_probabilities)
 
    # Get the class name using the retrieved index.
    predicted_class_name = CLASSES_LIST[predicted_label]
    
    # Display the predicted class along with the prediction confidence.
    print(f'Predicted: {predicted_class_name}\nConfidence: {predicted_labels_probabilities[predicted_label]}')
        
    video_reader.release()
    
    return str(predicted_class_name),"Your uploaded video detectes the "+str(predicted_class_name)+" Activity with Confidence level : "+str(predicted_labels_probabilities[predicted_label])+"."
        
@app.route("/checkRegister",methods=['POST','GET'])
def checkRegister():   
    if request.method == "POST": 
        details = request.form
        
        fullname = details['fullname']
        username = details['username']  
        email = details['email']
        mobile = details['mobilenumber']
        password = details['password']
        
        cursor.execute('SELECT * FROM register WHERE fname = %s and username = %s', (fullname,username))
        count = cursor.rowcount
        print(count)
        if count > 0: 
            return "fail"      
        else:               
            sql1 = "INSERT INTO register(fname,username,email,mobile,password)VALUES(%s,%s,%s,%s,%s);"
            val1 = (fullname,username,email,mobile,password)
            cursor.execute(sql1,val1)
            con.commit()
            return "success"  

@app.route('/validatelogin',methods=['POST','GET'])
def validatelogin():
    if request.method == "POST":
        details = request.form
        
        username = details['username']
        password = details['password'] 
        
        cursor.execute('SELECT * FROM register WHERE username = %s and password = %s', (username,password))
        count = cursor.rowcount
        if count > 0:
            cardData= cursor.fetchone() 
            session['userfname'] = cardData[1]
            session['useremail'] = cardData[3]
            session['userpass'] = cardData[5]
            return "success"      
        else:  
            return "fail" 

@app.route("/uploadfile",methods=['POST','GET'])
def uploadfile():    
    return render_template('uploadFile.html')
            
@app.route('/detectactivity',methods=['POST','GET'])
def detectactivity():
    if request.method == "POST":
        
        file= request.files['volunteer-file'] 
        
        file.save("static/uploaded-video.mp4")
        
        input_video_file_path = "static/uploaded-video.mp4"
        
        # Perform Single Prediction on the Test Video.
        returntext, status = predict_video(input_video_file_path, SEQUENCE_LENGTH)
        
        print()
        print(returntext)
        print()
        if returntext == 'Suspicious':   
            print()
            print(session.get("userpass"))
            print(session.get("useremail"))
            print()
            input_video_file = input_video_file_path
            output_zip_file = 'video.zip'   
            passwordforlock = session.get("userpass")
            
            zip_with_password(input_video_file, output_zip_file, passwordforlock.encode())
            
            useremail = session.get("useremail")
            sendvideofilemailtouser(useremail,output_zip_file)
        
        return status 
    return render_template('uploadFile.html') 

if __name__ == '__main__':
    app.run('0.0.0.0')
    # app.run(debug=True)