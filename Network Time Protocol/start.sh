#!/bin/bash

# Display the dramatic introduction
cat << "EOF"
========================================================================
                      CLOCK SYNCHRONIZATION EMERGENCY
========================================================================

Monocarp, Polycarp, and Pak Chenak are three students frantically 
working to complete their major project. Unfortunately, they've discovered 
their computers are showing different times, causing confusion about when 
assignments are actually due.

"We have no idea when to submit our work!" Monocarp complained during 
their emergency video call. "My computer says it's 3:15, but Polycarp's 
shows 3:22, and Pak Chenak's is somehow 20 minutes behind both of us!"

With the submission deadline approaching and no technical expertise among 
them, they've reached out to you for help. They need a way to synchronize 
their clocks to ensure they submit their work on time and avoid penalties.
========================================================================

EOF

# Ask for help
echo -n "Do you want to help these students? (yes/no): "
read answer

# Convert answer to lowercase
answer=$(echo "$answer" | tr '[:upper:]' '[:lower:]')

if [[ "$answer" == "yes" || "$answer" == "y" ]]; then
    echo "Thank you! Starting the clock synchronization system..."
    echo "Running docker compose to build and start the synchronization service..."
    docker compose up --build
else
    # Display more detailed sad crying ASCII art if the answer is no
    cat << "EOF"
    
    ╔══════════════════════════════════════════════════════════════════════╗
    ║  BREAKING NEWS: STUDENTS MISS DEADLINE DUE TO CLOCK SYNC FAILURE     ║
    ╚══════════════════════════════════════════════════════════════════════╝

                               .-"""-.
           _                 /        \               _
          |-|               |  o  o   |              |-|
     .----'-'----.  __      |    ^    |       __  .----'-'----.
    /____[CLOCK]___\||_\     \  '--'  /      /||_/____[CLOCK]___\
     | [] .-.-. [] |--' |     '.____.'      | '--| [] .-.-. [] |
     | [] '---' [] |    |    /        \     |    | [] '---' [] |
    ...MONOCARP....  ...POLYCARP...   ...PAK CHENAK...
       3:15           3:22              2:55

           ,;;;,   ,;;;,            ,;;;,      
          ;;;;;;;,;;;;;            ;;;;;;;     
     .:::.;;;;;;;;;;;;;.:.    .:::.;;;;;;;;;.::.
    ::::::`;;;;;;;;;':::::  :::::::`;;;;;';::::: 
    :::::::`;;;;;;'::::::: :::::::::`;;;;;::::::
    ::::::::`:_:':::::::::  :::::::::`;:::::::::
          ,;"|"|";;;,         ,;"'"|;;;,     
         %;;\|/\\;;%         %;;/|\;;;%     
         %;;;;;;;;;%         %;;;;;;;;%     
           `;;;;;'             `;;;;;'      

    "Our entire semester's work... GONE!" sobbed Monocarp.
    
    "If only someone had helped us synchronize our clocks," 
    cried Polycarp, tears streaming down his face.
    
    "We were just 3 minutes late with our submission..." 
    whispered Pak Chenak, staring blankly at the rejection email.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║         THE END: A TRAGEDY IN UNSYNCHRONIZED TIME                    ║
    ╚══════════════════════════════════════════════════════════════════════╝
EOF
fi
