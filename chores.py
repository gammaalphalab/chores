##########
# File:     chores.py
# Author:   Samuel James Bader
#           (samuel.james.bader@gmail.com)
# Revision: 4/10/2020
#
# Automates the assigning of weekly chores.
#
# The flow is to get people's preferences from an online Google Sheet,
# and ask the user which people and which chores should be done this week.
#
# At the beginning of each four-week-cycle, chore assignments are rotated.
# Then a "full optimization" takes place to find universally agreeable 
# loops of people who what to swap chores.
#
# Each of the three weeks thereafter, the relevant chores are pulled from the 
# cycle start, specific one-week chores only are rotated, and then a "partial
# optimization" takes place in which people who are displaced by the one-week
# chore adjustments have a chance to execute agreeable pairwise swaps.
#
# "Swaps" are only ever executed when all parties to the swap improved their
# misery ranking.  So this system is a guaranteed enhancement to a pure chore
# rotation, but is NOT a global optimizer.  It is, however, deterministic.
#
# After execution, an email is drafted as an HTML page which (if you're
# configured correctly), can open in a webpage for you to copy into your email
# software of choice, a history file is recorded, and a bar chart of the
# optimization results is produced.
#
# Additional features that would be nice but are not implemented yet:
#  1) New people have to do every chore once before they are allowed to swap
#     Currently I just "bias" that to happen by manually controlling new
#     people's preferences so that everything they haven't done yet is a 1
#     and everything they have is a 12.  Obviously could be better.
#  2) A way to set a specific person to a specific chore as is sometimes
#     appropriate at the discretion of the house manager (e.g. when it
#     connects to other on-going work the housemate is doing).  Currently, the
#     way to do that would be just pretend that person is out of town and
#     that chore does not need to be done, and let the rest get assigned, then
#     add the person back in.
#
##########


# Imports
import matplotlib.pyplot as plt
import requests as rs
import datetime
import numpy as np
from collections import deque
import random
import os
import shutil

# The misery spreadsheet is here
# https://docs.google.com/spreadsheets/d/
# 1hAq34ijA1pvcZZyv1So8rTvm2rzOfrDHion8INifApg/edit#gid=0
#
# We need a link to the TSV download for the spreadsheet
# I got this link by the following procedure:
# (1) Open the spreadsheet
# (2) File -> Download -> TSV
# (3) Open the downloads page (in Chrome, this is Control-J)
# (4) Right click the URL from this TSV download, and copy it
tsv_url="https://docs.google.com/spreadsheets/d/"\
        "1hAq34ijA1pvcZZyv1So8rTvm2rzOfrDHion8INifApg/export?"\
        "format=tsv&id=1hAq34ijA1pvcZZyv1So8rTvm2rzOfrDHion8INifApg&gid=0"


def get_preferences():
    """Returns the chore information from the misery spreadsheet.

    Uses tsv_url defined above to find the downloadable spreadsheet TSV.

    Returns:
        all_names: a list of strings, the initials of each person
        all_chores: a list of strings, the chore names
        prefs: a dict of preferences, accessed as prefs[PERSONNAME][CHORENAME] 
    """

    # Try to connect and retreive the data
    print("Fetching preferences",flush=True)
    res=rs.get(url=tsv_url)
    assert res.ok, "Request failed, check the URL and sheet permissions"

    # Get the names and chores from the retreived object
    # Don't include Wild as a chore, since that's filler for when there
    # are not enough chores
    lines=[l.decode('utf-8') for l in res.iter_lines()]
    data=[l.split('\t') for l in lines[1:] if l.split('\t')[0]!='']
    all_names=lines[0].split('\t')[1:]
    all_chores=[r[0] for r in data if r[0]!='Wild']

    # Form a dictionary of people's preferences
    prefs={}
    for i,n in enumerate(all_names):
        prefs[n]={}
        for r in data:
            p=float(r[1+i])

            # Validate each input number is between 1 and number of chores
            assert p>=1 and p<=(len(data))
            prefs[n][r[0]]=p

    # Success, return it
    print("Got preferences")
    return all_names, all_chores, prefs

def get_current_situation(all_names,all_chores):
    """Prompts user to find out who is in town and what chores are needed.

    Asks which residents are out of town and which chores to skip.
    Ensures that the number of residents is at least the number of chores.
    
    Args:
        all_names, all_chores: as returned by get_preferences

    Returns:
        names: a list of strings, names (initials) of people present
        chores: a list of strings, chores to do this weekend
    """

    # Print all names
    print("Listed residents are: ",", ".join(all_names))

    # Keep asking until we get a valid list of out-of-towners
    valid_input=False
    while valid_input is False:
        # Ask and interpret response as a comma-separated list
        oot=input("Is anyone out of town?"\
                " (comma-separated list of names, or just hit Enter): ")
        oot=[name.strip() for name in oot.strip().split(',') if name!='']

        # If any name in the response is not a housemate, warn and try again.
        valid_input=True
        for name in oot:
            if name not in all_names:
                print("Who is "+name+"!?")
                valid_input=False

    # Print who's here
    names=[name for name in all_names if name not in oot]
    print("Residents in town:    ",", ".join(names))

    # Print the person count and total chore count
    lnames=len(names)
    lchores=len(all_chores)
    print("There are "+str(lnames)+" people and "+str(lchores)+" chores.")
   
    # If we have same number of chores as people, we good
    if lnames==lchores:
        print("That's perfect.")
        print("Chores list is: "+", ".join(chores))
        chores=all_chores[:]

    # If we have more people than chores, add wildcards
    elif lnames>lchores:
        print("Adding in wildcards.")
        chores=all_chores[:] + ['Wild']*(lnames-lchores)
        print("Chores list is: "+", ".join(chores))

    # If we have more chores than people, we'll need to skip some
    else:

        # Remind user of the list
        print("Chores list is: "+", ".join(all_chores))

        # Keep asking until we get a valid set of chores to skip
        valid_input=False
        while valid_input is False:

            # Ask and interpret response as a comma-separated chore list
            sk=input("Which chores to skip? (comma-separated list, or just hit Enter): ")
            sk=[chore.strip() for chore in sk.strip().split(',') if chore!='']

            # If one chore name does not make sense, warn and ask again
            valid_input=True
            for chore in sk:
                if chore not in all_chores:
                    print("What is "+chore+"!?")
                    valid_input=False

            # If this skips the wrong number of chores, warn and ask again
            if len(sk)!=(lchores-lnames):
                print("Must skip exactly "+str((lchores-lnames))+" chores.")
                valid_input=False

        # Remove those unwanted chores from the list and print
        chores=[chore for chore in all_chores if chore not in sk]
        print("Chores list is: "+", ".join(chores))

    # Success, return
    return names, chores


def weekinfo():
    """Returns some useful info about the present week.

    The code assumes it's being run to assign chores "this weekend",
    where the date meant by "this weekend" switches over on every Monday.
    So this function just returns a bunch of attributes of this week.

    Returns: 
        fourweekno: a counter that increases after every four Mondays
        weekno: a counter that increases after every Monday
        mon: the date object of this week's Monday
        moncy: the date object of this four-week-cycle's Monday

    """
    # Arbirary Monday long ago
    epoch=datetime.date(2018,1,8)
    today=datetime.date.today()#-datetime.timedelta(7)

    # Calculate the "fourweek number", ie the number of entire fourweeks that have elapsed
    fourweekno=int(np.floor(((today-epoch).days)/(4*7)))

    # Calculate the "week number", ie the number of entire weeks that have elapsed
    weekno=int(np.floor(((today-epoch).days)/7))

    # Monday of this week
    mon=epoch+datetime.timedelta(7*weekno)

    # Monday of this cycle
    moncy=epoch+datetime.timedelta(7*4*fourweekno)

    return fourweekno, weekno, mon, moncy

def read_history():
    """Reads the current history file and returns its contents.

    The history is in 'history.txt' and contains what chore everyone did ever.
    Each row of the file is first, a date YYYY-MM-DD for the Monday of a week,
    followed by a sequence of INITIAL1:CHORE1,INITIALS2:CHORE2... indicating
    what each person did.

    Returns:
        hist: a list of rows in the history file, each row is a list of
            (1) a date object for the relevant Monday, and (2) a dict
            mapping each person to their chore.
    """

    # If there's no history, don't complain, it's an empty list
    if not os.path.exists("history.txt"):
        return []

    # Otherwise open up
    with open("history.txt",'r') as f:
        hist=[]

        # Split each line
        for line in f:
            mon,assig=line.split(',',1)
            
            # Form a date object, assemble a dict, and add it to the list
            mon=datetime.date(*[int(x) for x in mon.split('-')])
            hist+=[[
                mon,
                dict([x.strip().split(':') for x in assig.split(',')])]]
        return hist

def get_from_current_cycle(hist,moncy,names,chores):
    """ Gets the chore assignments baseline for this cycle. 

    Checks the hist to pull the chores associated to this cycle's Monday.
    People who are in names (ie THIS weeks housemates) and did chores at
    the beginning of the cycle will have whatever they already had.  But
    people who were not in the baseline or did chores that are not selected
    for this week will receive unassigned chores that are selected for this
    week.

    Arguments:
        hist: as returned from read_history
        moncy: as returned from weekinfo
        names, chores: the names and chores of interest for THIS WEEK

    Returns:
        chores:
            a list of chores (the "baseline") ordered to correspond with
            the list of names
    """

    # Extract the names & chores associated with the Monday that was
    # the beginning of this cycle.  If that doesn't exist, complain!
    gotem=False
    for h in reversed(hist):
        if h[0]==moncy:
            cc_names,cc_chores=zip(*list(h[1].items()))
            gotem=True
            break
    assert gotem, "Current chore cycle doesn't exist in records"

    # Select from those only the people and chores that are appropriate
    # for this week
    cc_names,cc_chores=\
        [list(x) for x in
            zip(*[(name,chore) for name,chore in
                zip(cc_names,cc_chores) if name in names])]

    # Attach a number onto the end of each wildcard chore so they are unique
    nwild=0
    for i,chore in enumerate(cc_chores):
        if chore=="Wild":
            nwild+=1
            cc_chores[i]="Wild"+str(nwild)

    # Copy this week's chores list so we can do the same with its wildcards
    chores=chores.copy()
    nwild=0
    for i,chore in enumerate(chores):
        if chore=="Wild":
            nwild+=1
            chores[i]="Wild"+str(nwild)
    
    # List of chores in this week but not cycle start
    extra_chores=[chore for chore in chores if chore not in cc_chores]

    # This will contain a valid chore assignment for this week
    # based on the cycle start
    new_chores=[]

    # Go through the current names in order
    for name in names:

        # If person was in the cycle start
        if name in cc_names:

            # and if their chore is valid this week
            cc_chore=cc_chores[cc_names.index(name)]
            if cc_chore in chores:

                # then given them that chore
                new_chores+=[cc_chore]

            # but if their previous chore is not valid this week
            else:

                # they get a new chore from extra_chores
                new_chores+=[extra_chores[0]]
                extra_chores=extra_chores[1:]

        # or if they were not in the cycle start
        else:

            # they get a new chore from extra_chores
            new_chores+=[extra_chores[0]]
            extra_chores=extra_chores[1:]

    # Strip the numbers off the wild chores
    for i,chore in enumerate(new_chores):
        if "Wild" in chore:
            new_chores[i]="Wild"

    # Success, return
    return new_chores

def print_chores(names,chores):
    """Prints a table of people and chores."""
    for name,chore in zip(names,chores):
        print("{:5s} - {:15s}".format(name,chore))

def seek_loop(names,chores,prefs,
        curr_person,people_already_included=[],improvement_so_far=0,
        largeloop=True):
    """Attempts to find a universally-agreeable chore swap.

    This function works recursively, starting with one specified person
    (curr_person) who looks for other chores he'd rather have.  Then
    this function will be called recursively on the other people who have
    the chores that the curr_person wants, and each recursion continues
    until either it makes it back to the initial curr_person, completing
    a loop, or is unable to form a complete loop.  Whenever multiple
    directions are possible, all are taken and the maximum reported.

    To rule out trival swaps, a person will only be willing to swap to a
    chore with the same level of misery if they are part of a recursive branch
    that *already* offers some improvement to someone, ie the first person will
    not try to trade for evenly hated chores.

    Args:
        names, chores: the current names and correspondingly ordered chores
        prefs: as returned by get_preferences
        curr_person: the person who starts the loop by looking to get a
            different chore
        people_already_included: people who already appear in the recursive
            branch so far, so should not be considered as options while on
            this branch
        improvement_so_far: amount of improvement already realized for the
            people in this branch if the branch succeeds in becoming a loop
        largeloop: if False, subverts the algorithm to never go past two
            people, ie only seek pairwise swaps

    Returns:
        loop: a list of people such that the chore should rotate from each
            person to the previous, and from the first person to the last
        improvment: the total improvement in misery from making this change

        (if no branch is found, returns [False,0])

    """

    # index of the current person in the names list, and their current misery
    i_name=names.index(curr_person)
    current_misery=prefs[curr_person][chores[i_name]]

    # list of people whose chores the current person wants
    desired_switches=[names[i] for i,c in enumerate(chores)\

                    # can only include people not already in the branch
                    if (names[i] not in\
                        [curr_person]+people_already_included[1:]) \

                    # and don't make even trades at the beginning of a branch 
                    and prefs[curr_person][c]<=
                        current_misery-1e-10*(improvement_so_far==0)]
    
    # Will be a list of [loop,improvement] for possible branches
    possibilities=[]

    # Go through each of the potential switchees
    for n in desired_switches:

        # If this would form a complete loop
        if len(people_already_included) and (n == people_already_included[0]):

            # Add it to possibilities
            possibilities+=[[people_already_included+[curr_person],
                             improvement_so_far\
                                 +current_misery\
                                 -prefs[curr_person][chores[names.index(n)]]]]

        # If we're still on the initial person
        # or we're not restricted to pairwise swaps
        elif largeloop or (not len(people_already_included)):

            # Then recurse to find the best branch from there
            found=seek_loop(names,chores,prefs,
                        n,people_already_included+[curr_person],\
                     improvement_so_far\
                        +current_misery-prefs[curr_person][chores[names.index(n)]],
                     largeloop=largeloop)

            # If a branh is found, add it to possibilities
            if found[0]:
                possibilities+=[found]

    # If we have possibilities, return the best one
    if len(possibilities):
        return possibilities[np.argmax([p[1] for p in possibilities])]

    # Otherwise return the sad news
    else:
        return False,0

def misery(names,chores,prefs):
    """Computes the total misery of this chore assignment."""
    return sum(prefs[n][c] for n,c in zip(names,chores))/len(chores)

def show_arrangement(names,chores,prefs):
    """Makes a misery bar chart in Misery.png.
    
    Args:
        names, chores: the current chore assignment
        prefs: as returned by get_preferences
    """
    plt.bar(names,[prefs[n][chores[i]] for i,n in enumerate(names)])
    plt.ylim(0,len(chores))
    plt.ylabel("Misery")
    plt.savefig("Misery.png")

def show_improvement(names,chores,oldchores,prefs):
    """Makes a misery chart in Misery.png comparing old and new assignment.
    
    Args:
        names, chores: the current chore assignment
        oldchores: the unimproved assignment
        prefs: as returned by get_preferences
    """
    ind=np.arange(len(names))
    width=.35
    plt.bar(ind,[prefs[n][oldchores[i]] for i,n in enumerate(names)],
            width,color='lightcoral',label='Before swap')
    plt.bar(ind+width,[prefs[n][chores[i]] for i,n in enumerate(names)],
            width,color='deepskyblue',label='After swap')
    plt.xticks(ind+width/2,names)
    plt.legend(loc='best')
    plt.ylim(0,np.max([np.max(list(prefs[n].values())) for n in names]))
    plt.ylabel("Misery")
    for i,n,c,oc in zip(ind,names,chores,oldchores):
        plt.text(i,0.1,oc,rotation=90,ha='center',va='bottom')
        plt.text(i+width,0.1,c,rotation=90,ha='center',va='bottom')
    plt.savefig("Misery.png")
    

def improve(names,chores,prefs,restricted_askers=None,largeloop=True):
    """Seeks to find the universally agreeable swaps available.

    Essentially calls seek_loop for everyone in the list on repeat until
    every call comes up empty.  The order to go through and ask people to seek
    loops is determined by who has the most misery, which gives them a first
    chance to improve their lot.

    Args:
        names, chores: the current chore assignment
        prefs: as returned from get_preferences
        restricted_askers: if supplied, these are the only people who will try
            to start seeking a loop
        largeloop: see seek_loop, can force only pairwise swaps
    """
    # Copy the current chores list so we don't change an argument
    chores=chores.copy()

    # List of people who can start loops
    restricted_askers=restricted_askers if restricted_askers else names

    # Order the list of loop starters by current misery
    asking_order=list(sorted(restricted_askers,
        key=lambda n:-prefs[n][chores[names.index(n)]]))

    # Records of misery updating after each swap
    historical_misery=[misery(names,chores,prefs)]
    print("Current misery: ",misery(names,chores,prefs))


    # Keep trying to make trades
    while True:

        # Resets to False after every pass through the asking order
        made_trade=False
        for n in asking_order:

            # Did we find one?
            loop,improvement  =\
                    seek_loop(names,chores,prefs,n,largeloop=largeloop)
            if not loop: continue

            # If so, update the chores list
            print("Executing trade ","  <-  ".join(loop+[loop[0]]))
            nchore = chores[names.index(n)]
            for nget,ngive in zip(loop[:-1],loop[1:]):
                chores[names.index(nget)]=chores[names.index(ngive)]
            chores[names.index(loop[-1])]=nchore

            # And update the misery records
            historical_misery+=[misery(names,chores,prefs)]
            print("Current misery: ",misery(names,chores,prefs))
            made_trade=True

        # If we made it through a full round of asking order with no trades
        if not made_trade:

            # Then we're done
            break

    # Success, return
    return chores

def make_email(names,chores,weekno,mon):
    """Writes out and opens the email for the given assignment.
   
    Outputs to a file called email.html the contents of a message to the house
    about chore assignments.  Calls "google-chrome" to open that file in the
    browser.  This last part works on my system (Ubuntu linux with Chrome
    installed), but may have to be tweaked to generalize.  If it doesn't work
    for you, oh well, just open this folder and double-click email.html.

    Args:
        names, chores: the chore assignment
        weekno: as returned by weekinfo
    """
    with open("email.html",'w') as f:

        # Get the date of this upcoming Friday
        friday=mon+datetime.timedelta(4-mon.weekday())

        # Write the title with this Friday's date
        f.write("<html><head><title>Chores "\
                +friday.strftime("%m/%d")+"</title></head>")
        f.write("<h1>Chore Assignments "\
                +friday.strftime("%m/%d")+"</h1>")

        # Greeting
        f.write("Hi Housemates,<br/><br/>")
        f.write("Below are this weekend's chore assignments!<br/>")

        # Advisory about the week number in the cycle
        if (weekno%4)+1==4:
            f.write("(Last week of this cycle,"\
                    " so make sure once-per-rotation items get done!)"\
                    "<br/><br/>")
        else:
            f.write("(Week #"+str((weekno%4)+1)+" of this chore cycle.)"\
                    "<br/><br/>")
        
        # Table of chores
        f.write("<table>")
        f.write("<tr><th>{:5s}</th><th>{:15s}</th></tr>"\
                .format("Name","Chore"))
        for name,chore in zip(names,chores):
           f.write("<tr><td>{:5s}</td><td>{:15s}</td></tr>"\
                   .format(name,chore))
        f.write("</table><br/>")

        # Link to the misery spreadsheet
        f.write("Your <a href='"+tsv_url.split("/export?")[0]+\
                "'>chore preferences</a>"\
                " can be updated at any time.<br/><br/>")

        # Signoff
        f.write("Cheers,<br/>House Manager")

        # Styling for the table 
        f.write("<style>")
        f.write("table {border-collapse: collapse;}")
        f.write("td {border: 1px solid #ddd;}")
        f.write("th{background-color: skyblue;}")
        f.write("tr:nth-child(even){background-color: #f2f2f2;}")
        f.write("</style></html>")

    # Try to open the email in a browser
    os.system("google-chrome email.html")

def add_to_history(hist,mon,names,chores):
    """Adds a new chore assignment to the history.

    See read_history() for the format of the file.

    Args:
        hist: the current history as returned by read_history
        mon: the Monday date object for this week
        names, chores: the new chore assignment
    """

    # If this week is already recorded in history, overwrite it
    if len(hist) and hist[-1][0]==mon:
        print("Overwriting this week in history")
        hist[-1]=[mon,dict(zip(names,chores))]

    # Otherwise add it to the hist object
    else:
        print("Adding this week into history")
        hist+=[  [mon,dict(zip(names,chores))]]

    # Make a backup of the history.txt file
    if os.path.exists("history.txt"):
        shutil.copyfile('history.txt','history_bk'+str(datetime.date.today())+'.txt')

    # Output to the file
    with open("history.txt",'w') as f:
        for line in hist:
            print(str(line[0])+','+','.join([k+':'+v for k,v in line[1].items()]),file=f)


def main():
    """Runs everything as described at the top."""

    # Get the preferences from the Misery spreadsheet
    all_names, all_chores, prefs=get_preferences()

    # Narrow down to what people and chores we want this week
    names, chores=get_current_situation(all_names,all_chores)
    del all_names, all_chores
    print("\n\n")

    # Get the info for this week and the history
    fourweekno,weekno,mon,moncy=weekinfo()
    hist=read_history()

    # If it's the start of a cycle, rotate chores by the fourweekno
    # then be prepared to do a full Pareto improvement
    if (weekno % 4)==0:
        print("It's the start of a chore cycle")
        chores=deque(chores)
        chores.rotate(fourweekno % len(chores))
        chores=list(chores)
        do_full_improvement=True
    
    # Otherwise, get the chores from the beginning of the cycle
    # and be prepared to do only pairwise-swap Pareto improvement
    # of people who get bumped by one-week-long chores
    else:
        print("Continuing chore cycle, weekno=",str(weekno))
        try:
            chores=get_from_current_cycle(hist,moncy,names,chores)
            do_full_improvement=False

        # If can't get beginning of chore cycle, fall back to
        # the new-chore-cycle scheme
        except:
            print("Chore cycle doesn't seem to exist, making new one.")
            chores=deque(chores)
            chores.rotate(fourweekno % len(chores))
            chores=list(chores)
            do_full_improvement=True

        # Print the baseline as from the beginning of the cycle
        print("Here's the cycle baseline applied to this week")
        print_chores(names,chores)

        # For chores that rotate weekly (Wild, Lawn, Dishes),
        # bump each to the next person.  People who are affected by
        # this bumping go in the "sad" list
        sad=[]
        for chore in ['Wild','Lawn','Dishes']:
            for i in [i for (i,c) in enumerate(chores) if c==chore]:
                print('Rotating',chore,'by',((weekno)%(len(chores)-1)+1))
                i2=(i+((weekno)%(len(chores)-1)+1))%len(chores)
                chores[i]=chores[i2]
                chores[i2]=chore
                if names[i] not in sad:
                    sad+=[names[i]]
                if names[i2] not in sad:
                    sad+=[names[i2]]
        if len(sad): print("Disturbed people:",",".join(sad))

    # After all those rotations/bumps, print the "initial condition"
    # before performing optimization
    print("Here's the initial condition")
    print_chores(names,chores)
    oldchores=chores[:]

    # Do optimization to the extent requested
    if do_full_improvement:
        print("Attempting a full improvement")
        chores=improve(names,chores,prefs)
    else:
        print("Attempting a single-switch improvement")
        chores=improve(names,chores,prefs,restricted_askers=sad,largeloop=False)

    # Print the final assignments
    print("Here's the final condition")
    print_chores(names,chores)

    # Add to history, make a chart, and make the email
    add_to_history(hist,mon,names,chores)
    show_improvement(names,chores,oldchores,prefs)
    make_email(names,chores,weekno,mon)

# Go
if __name__=="__main__":
    main()
