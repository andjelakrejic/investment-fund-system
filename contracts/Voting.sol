// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Voting {
    mapping(address => bool) public allowedVoters;
    mapping(address => bool) public hasVoted;

    uint256 public approveVotes;
    uint256 public rejectVotes;
    uint256 public majority;

    bool public votingEnded;
    bool public approved;

    event VotingFinished(bool approved);

    constructor(address[] memory voters) {
        require(voters.length > 0, "No voters.");
        require(voters.length % 2 == 1, "Even number of voters.");

        majority = voters.length / 2 + 1;

        for (uint256 i = 0; i < voters.length; i++) {
            allowedVoters[voters[i]] = true;
        }
    }

    function vote(bool approve) external {
        require(!votingEnded, "Voting ended.");
        require(allowedVoters[msg.sender], "Invalid address.");
        require(!hasVoted[msg.sender], "Already voted.");

        hasVoted[msg.sender] = true;

        if (approve) {
            approveVotes++;
        } else {
            rejectVotes++;
        }

        if (approveVotes >= majority) {
            votingEnded = true;
            approved = true;

            emit VotingFinished(true);
        } else if (rejectVotes >= majority) {
            votingEnded = true;
            approved = false;

            emit VotingFinished(false);
        }
    }
}